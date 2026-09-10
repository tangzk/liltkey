#include "linebuffer.h"
#include "session.h"

#include <fcitx-config/configuration.h>
#include <fcitx-config/iniparser.h>
#include <fcitx-config/option.h>
#include <fcitx-utils/capabilityflags.h>
#include <fcitx-utils/event.h>
#include <fcitx-utils/eventloopinterface.h>
#include <fcitx-utils/handlertable.h>
#include <fcitx-utils/key.h>
#include <fcitx-utils/keysym.h>
#include <fcitx-utils/textformatflags.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/candidatelist.h>
#include <fcitx/event.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx/text.h>
#include <fcitx/userinterface.h>

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace voiceinput {
namespace {

constexpr char ConfigFile[] = "conf/voiceinput.conf";

std::uintptr_t contextId(fcitx::InputContext *inputContext) {
    return reinterpret_cast<std::uintptr_t>(inputContext);
}

std::string socketPath() {
    if (const char *runtimeDirectory = std::getenv("XDG_RUNTIME_DIR")) {
        if (*runtimeDirectory) {
            return std::string(runtimeDirectory) +
                   "/fcitx5-voice/service.sock";
        }
    }
    return "/run/user/" + std::to_string(::getuid()) +
           "/fcitx5-voice/service.sock";
}

} // namespace

FCITX_CONFIGURATION(
    VoiceInputConfig,
    fcitx::KeyListOption triggerKey{this,
                                    "TriggerKey",
                                    "Voice input hotkey",
                                    {fcitx::Key("Control+Alt+V")},
                                    fcitx::KeyListConstrain()};);

class VoiceInput final : public fcitx::AddonInstance {
public:
    explicit VoiceInput(fcitx::Instance *instance)
        : instance_(instance), input_(Session::MaxLineBytes - 1) {
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextKeyEvent,
            fcitx::EventWatcherPhase::PreInputMethod,
            [this](fcitx::Event &event) { handleActiveKey(event); }));
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextKeyEvent,
            fcitx::EventWatcherPhase::PostInputMethod,
            [this](fcitx::Event &event) { handleTriggerKey(event); }));

        auto cancel = [this](fcitx::Event &event) {
            auto &inputEvent = static_cast<fcitx::InputContextEvent &>(event);
            cancelFor(inputEvent.inputContext(), true);
        };
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextFocusOut,
            fcitx::EventWatcherPhase::Default, cancel));
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextReset,
            fcitx::EventWatcherPhase::Default, cancel));
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextSwitchInputMethod,
            fcitx::EventWatcherPhase::Default, cancel));
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextCapabilityChanged,
            fcitx::EventWatcherPhase::Default,
            [this](fcitx::Event &event) {
                auto &inputEvent =
                    static_cast<fcitx::InputContextEvent &>(event);
                const auto capabilities =
                    inputEvent.inputContext()->capabilityFlags();
                if (capabilities.test(fcitx::CapabilityFlag::Password) ||
                    capabilities.test(fcitx::CapabilityFlag::Sensitive)) {
                    cancelFor(inputEvent.inputContext(), true);
                }
            }));
        handlers_.emplace_back(instance_->watchEvent(
            fcitx::EventType::InputContextDestroyed,
            fcitx::EventWatcherPhase::Default,
            [this](fcitx::Event &event) {
                auto &inputEvent =
                    static_cast<fcitx::InputContextEvent &>(event);
                cancelFor(inputEvent.inputContext(), false);
            }));
        reloadConfig();
    }

    ~VoiceInput() override {
        if (boundContext_) {
            const auto message = session_.cancel(contextId(boundContext_));
            if (message) {
                bestEffortWrite(*message);
            }
        }
        closeTransport();
    }

    const fcitx::Configuration *getConfig() const override { return &config_; }

    void setConfig(const fcitx::RawConfig &config) override {
        config_.load(config, true);
        fcitx::safeSaveAsIni(config_, ConfigFile);
    }

    void reloadConfig() override { fcitx::readAsIni(config_, ConfigFile); }

private:
    void handleTriggerKey(fcitx::Event &event) {
        auto &keyEvent = static_cast<fcitx::KeyEvent &>(event);
        if (keyEvent.isRelease() || keyEvent.filtered() ||
            !keyEvent.key().checkKeyList(config_.triggerKey.value())) {
            return;
        }
        keyEvent.filterAndAccept();
        start(keyEvent.inputContext());
    }

    void handleActiveKey(fcitx::Event &event) {
        auto &keyEvent = static_cast<fcitx::KeyEvent &>(event);
        if (keyEvent.isRelease() || !boundContext_ ||
            keyEvent.inputContext() != boundContext_) {
            return;
        }
        const auto id = contextId(boundContext_);
        if (keyEvent.key().checkKeyList(config_.triggerKey.value())) {
            keyEvent.filterAndAccept();
            if (auto request = session_.toggle(id)) {
                queue(*request);
            }
            // Connecting/Starting toggles cancel immediately. The state is
            // already idle even when there was a cancel frame to send, so the
            // input-context pointer must be dropped on both paths.
            if (session_.phase() == Phase::Idle) {
                closeTransport();
                auto *context = boundContext_;
                clearUi(context);
                boundContext_ = nullptr;
            }
            updateUi(boundContext_);
            return;
        }
        if (keyEvent.key().check(FcitxKey_Escape)) {
            keyEvent.filterAndAccept();
            cancelFor(boundContext_, true);
            return;
        }
        if (session_.phase() == Phase::Preview) {
            if (keyEvent.key().check(FcitxKey_Return) ||
                keyEvent.key().check(FcitxKey_KP_Enter)) {
                keyEvent.filterAndAccept();
                auto *context = boundContext_;
                if (context->hasFocus()) {
                    if (auto text = session_.commit(id)) {
                        context->commitString(*text);
                    }
                } else {
                    session_.cancel(id);
                }
                if (boundContext_ != context) {
                    return;
                }
                clearUi(context);
                boundContext_ = nullptr;
                return;
            }
            if (keyEvent.key().check(FcitxKey_BackSpace)) {
                keyEvent.filterAndAccept();
                session_.backspace(id);
                updateUi(boundContext_);
                return;
            }
        }
        if (!keyEvent.key().isModifier()) {
            // Give the ordinary key to the active input method, but first
            // invalidate this voice session so it can never later commit over
            // the composition started by that key.
            cancelFor(boundContext_, true);
        }
    }

    bool allowedToStart(fcitx::InputContext *context) const {
        if (!context || !context->hasFocus()) {
            return false;
        }
        const auto capabilities = context->capabilityFlags();
        if (capabilities.test(fcitx::CapabilityFlag::Password) ||
            capabilities.test(fcitx::CapabilityFlag::Sensitive)) {
            return false;
        }
        const auto &panel = context->inputPanel();
        return panel.preedit().empty() && panel.clientPreedit().empty() &&
               !panel.candidateList();
    }

    void start(fcitx::InputContext *context) {
        if (!allowedToStart(context) || session_.phase() != Phase::Idle) {
            return;
        }
        const std::string id = std::to_string(::getpid()) + "-" +
                               std::to_string(++nextSessionId_);
        if (!session_.begin(id, contextId(context))) {
            return;
        }
        boundContext_ = context;
        updateUi(context);
        if (!openTransport()) {
            failTransport("语音服务不可用");
        }
    }

    bool openTransport() {
        closeTransport();
        fd_ = ::socket(AF_UNIX, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
        if (fd_ < 0) {
            return false;
        }
        const std::string path = socketPath();
        if (path.size() >= sizeof(sockaddr_un::sun_path)) {
            closeTransport();
            return false;
        }
        sockaddr_un address{};
        address.sun_family = AF_UNIX;
        std::memcpy(address.sun_path, path.c_str(), path.size() + 1);
        const int result = ::connect(fd_, reinterpret_cast<sockaddr *>(&address),
                                     sizeof(address));
        if (result < 0 && errno != EINPROGRESS) {
            closeTransport();
            return false;
        }
        connecting_ = result < 0;
        ioEvent_ = instance_->eventLoop().addIOEvent(
            fd_, watchFlags(),
            [this](fcitx::EventSourceIO *, int,
                   fcitx::IOEventFlags flags) { return onSocket(flags); });
        handshakeTimer_ = instance_->eventLoop().addTimeEvent(
            CLOCK_MONOTONIC, fcitx::now(CLOCK_MONOTONIC) + 5000000, 0,
            [this](fcitx::EventSourceTime *, std::uint64_t) {
                if (session_.phase() == Phase::Connecting ||
                    session_.phase() == Phase::Starting) {
                    failTransport("语音服务握手超时");
                }
                return false;
            });
        return true;
    }

    fcitx::IOEventFlags watchFlags() const {
        fcitx::IOEventFlags flags;
        flags |= fcitx::IOEventFlag::In;
        flags |= fcitx::IOEventFlag::Err;
        flags |= fcitx::IOEventFlag::Hup;
        if (connecting_ || !output_.empty()) {
            flags |= fcitx::IOEventFlag::Out;
        }
        return flags;
    }

    void updateWatch() {
        if (ioEvent_) {
            ioEvent_->setEvents(watchFlags());
        }
    }

    bool onSocket(fcitx::IOEventFlags flags) {
        if (connecting_ && ((flags & fcitx::IOEventFlag::Out) ||
                            (flags & fcitx::IOEventFlag::In) ||
                            (flags & fcitx::IOEventFlag::Err))) {
            int error = 0;
            socklen_t length = sizeof(error);
            if (::getsockopt(fd_, SOL_SOCKET, SO_ERROR, &error, &length) < 0 ||
                error != 0) {
                failTransport("语音服务不可用");
                return false;
            }
            connecting_ = false;
        }
        if (fd_ >= 0 && (flags & fcitx::IOEventFlag::Out) && !flush()) {
            failTransport("语音服务连接失败");
            return false;
        }
        if (fd_ >= 0 && (flags & fcitx::IOEventFlag::In) && !readAvailable()) {
            failTransport("语音服务连接失败");
            return false;
        }
        if (fd_ >= 0 && ((flags & fcitx::IOEventFlag::Err) ||
                         (flags & fcitx::IOEventFlag::Hup))) {
            failTransport("语音服务已断开");
            return false;
        }
        updateWatch();
        return fd_ >= 0;
    }

    bool readAvailable() {
        char bytes[4096];
        while (true) {
            const ssize_t size = ::recv(fd_, bytes, sizeof(bytes), 0);
            if (size > 0) {
                auto result = input_.feed(
                    std::string_view(bytes, static_cast<std::size_t>(size)));
                if (result.overflow) {
                    return false;
                }
                for (auto &line : result.lines) {
                    handleLine(line);
                    if (fd_ < 0) {
                        return true;
                    }
                }
                continue;
            }
            if (size == 0) {
                return false;
            }
            if (errno == EINTR) {
                continue;
            }
            return errno == EAGAIN || errno == EWOULDBLOCK;
        }
    }

    void handleLine(const std::string &line) {
        auto *context = boundContext_;
        if (!context || !session_.activeFor(contextId(context)) ||
            !context->hasFocus()) {
            cancelFor(context, false);
            return;
        }
        const auto id = contextId(context);
        const Phase before = session_.phase();
        if (auto request = session_.handleLine(line)) {
            queue(*request);
            if (boundContext_ != context) {
                return;
            }
        }
        if (auto commit = session_.takeCommit()) {
            if (!session_.activeFor(id) || boundContext_ != context ||
                !context->hasFocus()) {
                cancelFor(context, false);
                return;
            }
            clearUi(context);
            if (boundContext_ != context || !session_.activeFor(id) ||
                !context->hasFocus()) {
                return;
            }
            if (!commit->empty()) {
                context->commitString(*commit);
                if (boundContext_ != context || !session_.activeFor(id)) {
                    return;
                }
            }
        }
        if ((session_.phase() == Phase::Recording ||
             session_.phase() == Phase::Idle) &&
            handshakeTimer_) {
            handshakeTimer_.reset();
        }
        if (session_.phase() == Phase::Preview) {
            closeTransport();
            updateUi(context);
            return;
        }
        if (before != Phase::Idle && session_.phase() == Phase::Idle) {
            closeTransport();
            if (auto error = session_.takeError()) {
                showStatus(context, *error);
            } else {
                clearUi(context);
            }
            boundContext_ = nullptr;
            return;
        }
        updateUi(context);
    }

    void queue(const std::string &message) {
        if (message.size() > Session::MaxLineBytes ||
            output_.size() + message.size() > Session::MaxLineBytes * 2) {
            failTransport("语音协议缓冲区超出限制");
            return;
        }
        output_ += message;
        if (!connecting_ && !flush()) {
            failTransport("语音服务连接写入失败");
            return;
        }
        updateWatch();
    }

    bool flush() {
        while (!output_.empty()) {
            const ssize_t size =
                ::send(fd_, output_.data(), output_.size(), MSG_NOSIGNAL);
            if (size > 0) {
                output_.erase(0, static_cast<std::size_t>(size));
                continue;
            }
            if (size < 0 && errno == EINTR) {
                continue;
            }
            return size < 0 && (errno == EAGAIN || errno == EWOULDBLOCK);
        }
        return true;
    }

    void bestEffortWrite(const std::string &message) {
        if (fd_ >= 0) {
            ::send(fd_, message.data(), message.size(), MSG_NOSIGNAL);
        }
    }

    void closeTransport() {
        handshakeTimer_.reset();
        ioEvent_.reset();
        if (fd_ >= 0) {
            ::close(fd_);
            fd_ = -1;
        }
        connecting_ = false;
        output_.clear();
        input_.clear();
    }

    void failTransport(const std::string &message) {
        auto *context = boundContext_;
        closeTransport();
        session_.abandon();
        if (context) {
            showStatus(context, message);
        }
        boundContext_ = nullptr;
    }

    void cancelFor(fcitx::InputContext *context, bool updateUi) {
        if (!context || context != boundContext_) {
            return;
        }
        if (session_.activeFor(contextId(context))) {
            if (auto request = session_.cancel(contextId(context))) {
                bestEffortWrite(*request);
            }
        }
        closeTransport();
        if (uiCallbackActive_) {
            context->inputPanel().reset();
        } else if (updateUi) {
            clearUi(context);
        }
        boundContext_ = nullptr;
    }

    bool updateClientPreedit(fcitx::InputContext *context) {
        if (!context || context != boundContext_ || !context->hasFocus()) {
            return false;
        }
        uiCallbackActive_ = true;
        context->updatePreedit();
        uiCallbackActive_ = false;
        return boundContext_ == context && context->hasFocus();
    }

    void updateInputPanel(fcitx::InputContext *context) {
        if (!context || context != boundContext_ || !context->hasFocus()) {
            return;
        }
        uiCallbackActive_ = true;
        context->updateUserInterface(
            fcitx::UserInterfaceComponent::InputPanel);
        uiCallbackActive_ = false;
    }

    void clearUi(fcitx::InputContext *context) {
        if (!context || context != boundContext_) {
            return;
        }
        context->inputPanel().reset();
        if (context->hasFocus() && updateClientPreedit(context)) {
            updateInputPanel(context);
        }
    }

    void showStatus(fcitx::InputContext *context,
                    const std::string &message) {
        if (!context || context != boundContext_ || !context->hasFocus()) {
            return;
        }
        context->inputPanel().reset();
        context->inputPanel().setAuxUp(fcitx::Text(message));
        if (updateClientPreedit(context)) {
            updateInputPanel(context);
        }
    }

    void updateUi(fcitx::InputContext *context) {
        if (!context || context != boundContext_ || !context->hasFocus()) {
            return;
        }
        context->inputPanel().reset();
        switch (session_.phase()) {
        case Phase::Connecting:
            context->inputPanel().setAuxUp(
                fcitx::Text("语音输入：正在连接…"));
            break;
        case Phase::Starting:
            context->inputPanel().setAuxUp(
                fcitx::Text("语音输入：正在启动录音…"));
            break;
        case Phase::Recording:
            context->inputPanel().setAuxUp(
                fcitx::Text("语音输入：录音中，再按快捷键结束"));
            break;
        case Phase::Stopping:
        case Phase::Transcribing:
            context->inputPanel().setAuxUp(
                fcitx::Text("语音输入：正在识别…"));
            break;
        case Phase::Preview: {
            auto candidates = std::make_unique<fcitx::CommonCandidateList>();
            candidates->append<fcitx::DisplayOnlyCandidateWord>(
                fcitx::Text(session_.preview()));
            candidates->setGlobalCursorIndex(0);
            context->inputPanel().setCandidateList(std::move(candidates));
            context->inputPanel().setAuxUp(
                fcitx::Text("语音输入：Enter 提交，Esc 取消"));
            break;
        }
        case Phase::Idle:
            return;
        }
        if (session_.streaming() && !session_.preview().empty()) {
            fcitx::Text preedit(session_.preview(),
                                fcitx::TextFormatFlag::Underline);
            preedit.setCursor(static_cast<int>(session_.preview().size()));
            if (context->capabilityFlags().test(
                    fcitx::CapabilityFlag::Preedit)) {
                context->inputPanel().setClientPreedit(preedit);
            } else {
                context->inputPanel().setPreedit(preedit);
            }
        }
        if (updateClientPreedit(context)) {
            updateInputPanel(context);
        }
    }

    fcitx::Instance *instance_;
    VoiceInputConfig config_;
    Session session_;
    fcitx::InputContext *boundContext_ = nullptr;
    std::uint64_t nextSessionId_ = 0;
    int fd_ = -1;
    bool connecting_ = false;
    bool uiCallbackActive_ = false;
    LineBuffer input_;
    std::string output_;
    std::unique_ptr<fcitx::EventSourceIO> ioEvent_;
    std::unique_ptr<fcitx::EventSourceTime> handshakeTimer_;
    std::vector<std::unique_ptr<
        fcitx::HandlerTableEntry<fcitx::EventHandler>>>
        handlers_;
};

class VoiceInputFactory final : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new VoiceInput(manager->instance());
    }
};

} // namespace voiceinput

FCITX_ADDON_FACTORY_V2(voiceinput, voiceinput::VoiceInputFactory)

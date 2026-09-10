// Real Fcitx5 instance and input contexts; a local fixture replaces only ASR.
#include <fcitx-utils/event.h>
#include <fcitx-utils/eventdispatcher.h>
#include <fcitx-utils/eventloopinterface.h>
#include <fcitx-utils/textformatflags.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addonmanager.h>
#include <fcitx/event.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>

#include <json-c/json.h>

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace fs = std::filesystem;

void require(bool ok, const char *message) {
    if (!ok) {
        throw std::runtime_error(message);
    }
}

class Context final : public fcitx::InputContext {
public:
    explicit Context(fcitx::InputContextManager &manager)
        : InputContext(manager, "voice-streaming-test") {
        created();
    }
    ~Context() override { destroy(); }

    const char *frontend() const override { return "voice-streaming-test"; }
    void commitStringImpl(const std::string &text) override {
        preeditAtCommit.emplace_back(inputPanel().clientPreedit().toString(),
                                     inputPanel().preedit().toString());
        commits.push_back(text);
        if (resetOnCommit) {
            reset();
        }
    }
    void deleteSurroundingTextImpl(int, unsigned int) override {}
    void forwardKeyImpl(const fcitx::ForwardKeyEvent &) override {}
    void updatePreeditImpl() override {
        if (resetOnUpdatePreedit) {
            resetOnUpdatePreedit = false;
            reset();
        }
    }

    bool key(const char *name) {
        fcitx::KeyEvent event(this, fcitx::Key(name));
        return keyEvent(event);
    }

    std::vector<std::string> commits;
    std::vector<std::pair<std::string, std::string>> preeditAtCommit;
    bool resetOnCommit = false;
    bool resetOnUpdatePreedit = false;
};

class Keyboard final : public fcitx::InputMethodEngine {
public:
    std::vector<fcitx::InputMethodEntry> listInputMethods() override {
        std::vector<fcitx::InputMethodEntry> entries;
        entries.emplace_back("keyboard-us", "Test keyboard", "en",
                             "keyboard");
        return entries;
    }
    void keyEvent(const fcitx::InputMethodEntry &, fcitx::KeyEvent &) override {}
};

class KeyboardFactory final : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *) override {
        return new Keyboard;
    }
};

class Fixture {
public:
    explicit Fixture(const fs::path &path) {
        fd_ = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        require(fd_ >= 0, "fixture socket failed");
        sockaddr_un address{};
        address.sun_family = AF_UNIX;
        std::strncpy(address.sun_path, path.c_str(),
                     sizeof(address.sun_path) - 1);
        require(bind(fd_, reinterpret_cast<sockaddr *>(&address),
                     sizeof(address)) == 0,
                "fixture bind failed");
        require(listen(fd_, 4) == 0, "fixture listen failed");
        thread_ = std::thread([this] { run(); });
    }

    ~Fixture() {
        stopping_ = true;
        shutdown(fd_, SHUT_RDWR);
        close(fd_);
        thread_.join();
    }

    std::atomic<int> starts{0};
    std::atomic<int> cancels{0};
    std::atomic<bool> allowFirstFinal{false};
    std::atomic<bool> allowFourthFinal{false};
    std::atomic<bool> allowFifthPartial{false};

private:
    static void sendLine(int client, const std::string &line) {
        const std::string value = line + "\n";
        send(client, value.data(), value.size(), MSG_NOSIGNAL);
    }

    static std::string jsonId(json_object *identifier) {
        return json_object_to_json_string_ext(identifier,
                                               JSON_C_TO_STRING_PLAIN);
    }

    void run() {
        while (true) {
            const int client = accept4(fd_, nullptr, nullptr, SOCK_CLOEXEC);
            if (client < 0) {
                return;
            }
            timeval timeout{2, 0};
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                       sizeof(timeout));
            sendLine(client, R"({"type":"ready","protocol":2})");
            std::string line;
            char ch = 0;
            int ordinal = 0;
            while (recv(client, &ch, 1, 0) == 1) {
                if (ch != '\n') {
                    line += ch;
                    continue;
                }
                json_object *object = json_tokener_parse(line.c_str());
                line.clear();
                if (!object) {
                    break;
                }
                json_object *type = nullptr;
                json_object *identifier = nullptr;
                json_object_object_get_ex(object, "type", &type);
                json_object_object_get_ex(object, "id", &identifier);
                if (!type || !identifier) {
                    json_object_put(object);
                    break;
                }
                const std::string kind = json_object_get_string(type);
                const std::string id = jsonId(identifier);
                json_object_put(object);

                if (kind == "start") {
                    ordinal = ++starts;
                    sendLine(client,
                             "{\"type\":\"recording\",\"id\":" + id + "}");
                    if (ordinal == 1) {
                        sendLine(client,
                                 "{\"type\":\"partial\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":1,\"text\":\"你\"}");
                        while (!allowFirstFinal.load() && !stopping_.load()) {
                            std::this_thread::sleep_for(
                                std::chrono::milliseconds(2));
                        }
                        if (stopping_) {
                            close(client);
                            return;
                        }
                        sendLine(client,
                                 "{\"type\":\"partial\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":2,\"text\":\"你好\"}");
                        sendLine(client,
                                 "{\"type\":\"final\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":3,\"text\":\"你好\"}");
                    } else if (ordinal == 2) {
                        sendLine(client,
                                 "{\"type\":\"partial\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":1,\"text\":\"面板预览\"}");
                    } else if (ordinal == 3) {
                        sendLine(client,
                                 "{\"type\":\"partial\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":1,\"text\":\"已提\"}");
                        sendLine(client,
                                 "{\"type\":\"final\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":2,\"text\":\"已提交\"}");
                    } else if (ordinal == 4) {
                        sendLine(client,
                                 "{\"type\":\"partial\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":1,\"text\":\"清除测试\"}");
                        while (!allowFourthFinal.load() && !stopping_.load()) {
                            std::this_thread::sleep_for(
                                std::chrono::milliseconds(2));
                        }
                        if (stopping_) {
                            close(client);
                            return;
                        }
                        sendLine(client,
                                 "{\"type\":\"final\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":2,\"text\":\"不应提交\"}");
                    } else if (ordinal == 5) {
                        while (!allowFifthPartial.load() && !stopping_.load()) {
                            std::this_thread::sleep_for(
                                std::chrono::milliseconds(2));
                        }
                        if (stopping_) {
                            close(client);
                            return;
                        }
                        sendLine(client,
                                 "{\"type\":\"partial\",\"id\":" + id +
                                     ",\"segment\":1,\"seq\":1,\"text\":\"重入预编辑\"}");
                    }
                } else if (kind == "stop" && ordinal == 1) {
                    sendLine(client,
                             "{\"type\":\"transcribing\",\"id\":" + id + "}");
                    sendLine(client,
                             "{\"type\":\"partial\",\"id\":" + id +
                                 ",\"segment\":2,\"seq\":4,\"text\":\"尾\"}");
                    sendLine(client,
                             "{\"type\":\"final\",\"id\":" + id +
                                 ",\"segment\":2,\"seq\":5,\"text\":\"尾音\"}");
                    sendLine(client,
                             "{\"type\":\"finished\",\"id\":" + id + "}");
                } else if (kind == "cancel") {
                    ++cancels;
                    sendLine(client,
                             "{\"type\":\"final\",\"id\":" + id +
                                 ",\"segment\":2,\"seq\":3,\"text\":\"迟到\"}");
                    sendLine(client,
                             "{\"type\":\"finished\",\"id\":" + id + "}");
                }
            }
            close(client);
        }
    }

    int fd_ = -1;
    std::thread thread_;
    std::atomic<bool> stopping_{false};
};

int main(int argc, char **argv) {
    require(argc == 2, "provide module path");
    char pattern[] = "/tmp/voice-streaming-it-XXXXXX";
    require(mkdtemp(pattern), "mkdtemp failed");
    const fs::path root(pattern);
    fs::create_directories(root / "data/fcitx5/addon");
    fs::create_directories(root / "config");
    fs::create_directories(root / "fcitx5-voice");
    setenv("XDG_DATA_HOME", (root / "data").c_str(), 1);
    setenv("XDG_CONFIG_HOME", (root / "config").c_str(), 1);
    setenv("XDG_RUNTIME_DIR", root.c_str(), 1);

    auto library = fs::absolute(argv[1]);
    library.replace_extension();
    std::ofstream(root / "data/fcitx5/addon/voiceinput.conf")
        << "[Addon]\nName=Voice Streaming Test\nType=SharedLibrary\n"
           "Category=Module\nOnDemand=False\nLibrary="
        << library.string() << "\n";

    int result = 1;
    {
        Fixture server(root / "fcitx5-voice/service.sock");
        char name[] = "voice-streaming-integration";
        char disable[] = "--disable=all";
        char enable[] = "--enable=voiceinput,keyboard";
        char *arguments[] = {name, disable, enable};
        fcitx::Instance instance(3, arguments);
        KeyboardFactory keyboardFactory;
        fcitx::StaticAddonRegistry registry{{"keyboard", &keyboardFactory}};
        instance.addonManager().registerDefaultLoader(&registry);

        std::unique_ptr<Context> clientPreeditContext;
        std::unique_ptr<Context> fallbackContext;
        std::unique_ptr<fcitx::EventSourceTime> timer;
        int stage = 0;
        const auto deadline = fcitx::now(CLOCK_MONOTONIC) + 5'000'000;
        instance.eventDispatcher().schedule([&] {
            require(instance.addonManager().addon("voiceinput"),
                    "absolute-path addon failed to load");
            clientPreeditContext =
                std::make_unique<Context>(instance.inputContextManager());
            fallbackContext =
                std::make_unique<Context>(instance.inputContextManager());
            clientPreeditContext->setCapabilityFlags(
                fcitx::CapabilityFlag::Preedit);
            clientPreeditContext->focusIn();
            require(clientPreeditContext->key("Control+Alt+v"),
                    "streaming trigger was not accepted");

            timer = instance.eventLoop().addTimeEvent(
                CLOCK_MONOTONIC, fcitx::now(CLOCK_MONOTONIC), 0,
                [&](fcitx::EventSourceTime *source, std::uint64_t) {
                    try {
                        require(fcitx::now(CLOCK_MONOTONIC) < deadline,
                                "streaming integration timed out");
                        if (stage == 0 &&
                            clientPreeditContext->inputPanel()
                                    .clientPreedit()
                                    .toString() == "你") {
                            const auto &text = clientPreeditContext->inputPanel()
                                                   .clientPreedit();
                            require(text.cursor() == 3,
                                    "Unicode client preedit cursor was not at end");
                            require(text.formatAt(0).test(
                                        fcitx::TextFormatFlag::Underline),
                                    "client preedit was not underlined");
                            server.allowFirstFinal = true;
                            stage = 1;
                        } else if (stage == 1 &&
                                   clientPreeditContext->commits ==
                                       std::vector<std::string>{"你好"}) {
                            require(clientPreeditContext->preeditAtCommit ==
                                        std::vector<std::pair<std::string,
                                                              std::string>>{
                                            {"", ""}},
                                    "preedit was not cleared before commit");
                            require(clientPreeditContext->inputPanel()
                                        .clientPreedit()
                                        .empty(),
                                    "final left client preedit visible");
                            clientPreeditContext->key("Control+Alt+v");
                            stage = 2;
                        } else if (stage == 2 &&
                                   clientPreeditContext->commits ==
                                       std::vector<std::string>{"你好", "尾音"}) {
                            clientPreeditContext->focusOut();
                            fallbackContext->focusIn();
                            require(fallbackContext->key("Control+Alt+v"),
                                    "fallback trigger was not accepted");
                            stage = 3;
                        } else if (stage == 3 &&
                                   fallbackContext->inputPanel()
                                           .preedit()
                                           .toString() == "面板预览") {
                            const auto &text =
                                fallbackContext->inputPanel().preedit();
                            require(fallbackContext->inputPanel()
                                        .clientPreedit()
                                        .empty(),
                                    "fallback unexpectedly used client preedit");
                            require(text.cursor() == 12,
                                    "fallback Unicode cursor was not at end");
                            require(text.formatAt(0).test(
                                        fcitx::TextFormatFlag::Underline),
                                    "fallback panel preedit was not underlined");
                            fallbackContext->key("Escape");
                            stage = 4;
                        } else if (stage == 4 && server.cancels >= 1) {
                            require(fallbackContext->commits.empty(),
                                    "cancelled fallback text was committed");
                            require(fallbackContext->inputPanel().empty(),
                                    "cancelled fallback left panel content");
                            fallbackContext->setCapabilityFlags(
                                fcitx::CapabilityFlag::Preedit);
                            fallbackContext->resetOnCommit = true;
                            fallbackContext->key("Control+Alt+v");
                            stage = 5;
                        } else if (stage == 5 && server.cancels >= 2) {
                            require(fallbackContext->commits ==
                                        std::vector<std::string>{"已提交"},
                                    "reset during commit lost or duplicated final");
                            require(fallbackContext->preeditAtCommit.back() ==
                                        std::pair<std::string, std::string>{"", ""},
                                    "reentrant commit observed stale preedit");
                            require(fallbackContext->inputPanel().empty(),
                                    "reentrant reset left stale voice UI");
                            fallbackContext->resetOnCommit = false;
                            fallbackContext->key("Control+Alt+v");
                            stage = 6;
                        } else if (stage == 6 &&
                                   fallbackContext->inputPanel()
                                           .clientPreedit()
                                           .toString() == "清除测试") {
                            fallbackContext->resetOnUpdatePreedit = true;
                            server.allowFourthFinal = true;
                            stage = 7;
                        } else if (stage == 7 && server.cancels >= 3) {
                            require(fallbackContext->commits ==
                                        std::vector<std::string>{"已提交"},
                                    "reset while clearing preedit committed stale text");
                            require(fallbackContext->inputPanel().empty(),
                                    "reset while clearing left stale voice UI");
                            fallbackContext->key("Control+Alt+v");
                            stage = 8;
                        } else if (stage == 8 && server.starts >= 5) {
                            fallbackContext->resetOnUpdatePreedit = true;
                            server.allowFifthPartial = true;
                            stage = 9;
                        } else if (stage == 9 && server.cancels >= 4) {
                            require(fallbackContext->inputPanel().empty(),
                                    "reset while publishing partial left stale voice UI");
                            fallbackContext->key("Control+Alt+v");
                            stage = 10;
                        } else if (stage == 10 && server.starts >= 6) {
                            require(fallbackContext->key("Escape"),
                                    "restart cancellation was not accepted");
                            stage = 11;
                        } else if (stage == 11 && server.cancels >= 5) {
                            result = 0;
                            instance.exit();
                            return false;
                        }
                    } catch (const std::exception &error) {
                        std::cerr << "stage " << stage << ": " << error.what()
                                  << " starts=" << server.starts
                                  << " cancels=" << server.cancels << '\n';
                        instance.exit();
                        return false;
                    }
                    source->setNextInterval(5'000);
                    source->setOneShot();
                    return true;
                });
        });
        instance.exec();
        timer.reset();
        fallbackContext.reset();
        clientPreeditContext.reset();
    }

    fs::remove_all(root);
    if (result == 0) {
        std::cout << "Fcitx5 streaming real-context integration passed\n";
    }
    return result;
}

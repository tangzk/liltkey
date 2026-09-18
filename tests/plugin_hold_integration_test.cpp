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
    void commitStringImpl(const std::string &text) override { commits.push_back(text); }
    void deleteSurroundingTextImpl(int, unsigned int) override {}
    void forwardKeyImpl(const fcitx::ForwardKeyEvent &) override {}
    void updatePreeditImpl() override {}

    bool key(const char *name, bool release = false) {
        fcitx::KeyEvent event(this, fcitx::Key(name), release);
        return keyEvent(event);
    }

    std::vector<std::string> commits;
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
        fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        sockaddr_un address{};
        address.sun_family = AF_UNIX;
        std::strncpy(address.sun_path, path.c_str(), sizeof(address.sun_path) - 1);
        require(bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0, "bind failed");
        require(listen(fd, 4) == 0, "listen failed");
        thread = std::thread([this] { run(); });
    }
    ~Fixture() { delay = false; shutdown(fd, SHUT_RDWR); close(fd); thread.join(); }
    std::atomic<int> starts{0}, stops{0}, cancels{0}, continuous{0};
    std::atomic<bool> delay{false};
private:
    void sendLine(int client, const std::string &line) {
        const auto frame = line + "\n";
        send(client, frame.data(), frame.size(), MSG_NOSIGNAL);
    }
    void run() {
        int client;
        while ((client = accept4(fd, nullptr, nullptr, SOCK_CLOEXEC)) >= 0) {
            timeval timeout{2, 0};
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
            sendLine(client, R"({"type":"ready","protocol":2})");
            std::string line;
            char ch;
            while (recv(client, &ch, 1, 0) == 1) {
                if (ch != '\n') { line += ch; continue; }
                auto *object = json_tokener_parse(line.c_str());
                line.clear();
                if (!object) break;
                auto *type = json_object_object_get(object, "type");
                auto *identifier = json_object_object_get(object, "id");
                const std::string kind = json_object_get_string(type);
                const std::string id = json_object_to_json_string(identifier);
                if (kind == "start") {
                    if (json_object_get_boolean(json_object_object_get(object, "continuous"))) ++continuous;
                    ++starts;
                    while (delay) std::this_thread::sleep_for(std::chrono::milliseconds(2));
                    sendLine(client, "{\"type\":\"recording\",\"id\":" + id + "}");
                } else if (kind == "stop") {
                    ++stops;
                    sendLine(client, "{\"type\":\"transcribing\",\"id\":" + id + "}");
                    sendLine(client, "{\"type\":\"final\",\"id\":" + id + ",\"segment\":1,\"seq\":1,\"text\":\"尾音\"}");
                    sendLine(client, "{\"type\":\"finished\",\"id\":" + id + "}");
                } else if (kind == "cancel") { ++cancels; }
                json_object_put(object);
            }
            close(client);
        }
    }
    int fd;
    std::thread thread;
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

        std::unique_ptr<Context> context;
        std::unique_ptr<fcitx::EventSourceTime> timer;
        int stage = 0;
        int result = 1;
        const auto deadline = fcitx::now(CLOCK_MONOTONIC) + 12'000'000;
        instance.eventDispatcher().schedule([&] {
            require(instance.addonManager().addon("voiceinput"), "addon failed to load");
            context = std::make_unique<Context>(instance.inputContextManager());
            context->focusIn();
            auto hold = [&] {
                context->key("Control_L");
                context->key("Control+Alt_L");
            };
            hold();
            context->key("Control+Alt+Alt_L", true); // quick tap
            timer = instance.eventLoop().addTimeEvent(CLOCK_MONOTONIC,
                fcitx::now(CLOCK_MONOTONIC) + 450000, 1000,
                [&](fcitx::EventSourceTime *source, uint64_t) {
                    try {
                        require(fcitx::now(CLOCK_MONOTONIC) < deadline, "hold test timed out");
                        if ((stage == 2 && server.starts < 1) ||
                            (stage == 4 && context->commits.size() < 1) ||
                            (stage == 5 && server.starts < 2) ||
                            (stage == 6 && context->commits.size() < 2) ||
                            (stage == 10 && server.starts < 3) ||
                            (stage == 11 && server.cancels < 1)) {
                            source->setNextInterval(5000); source->setOneShot(); return true;
                        }
                        switch (stage++) {
                        case 0:
                            require(server.starts == 0, "quick tap started recording");
                            context->key("Control_L"); context->key("Control+Alt_L");
                            context->key("Control+Alt+t");
                            break;
                        case 1:
                            require(server.starts == 0, "ordinary Ctrl+Alt shortcut started recording");
                            context->key("Control+Alt+Alt_L", true);
                            context->key("Control_L"); context->key("Control+Alt_L");
                            break;
                        case 2:
                            require(server.starts == 1 && server.continuous == 1, "hold did not start continuous recording");
                            context->key("Control+Alt+Alt_L"); // repeat must not toggle
                            break;
                        case 3:
                            require(server.stops == 0 && server.starts == 1, "held key toggled recording");
                            require(!context->key("Control+Alt+Control_L", true),
                                    "modifier release was swallowed after passing its press through");
                            require(!context->key("Alt_L", true), "remaining modifier release was swallowed");
                            break;
                        case 4:
                            require(server.stops == 1, "Ctrl release did not stop exactly once");
                            require(context->commits == std::vector<std::string>{"尾音"}, "release lost final audio");
                            context->key("Alt_R"); context->key("Alt+Control_R");
                            break;
                        case 5:
                            require(server.starts == 2, "reverse right-hand hold did not start");
                            context->key("Control+Alt+Alt_R", true);
                            break;
                        case 6:
                            require(server.stops == 2, "Alt release did not stop");
                            context->key("Control_L"); context->key("Control+Alt_L");
                            context->focusOut(); context->focusIn();
                            break;
                        case 7:
                            require(server.starts == 2, "focus out left pending hold armed");
                            context->key("Control_L"); context->key("Control+Alt_L");
                            context.reset();
                            context = std::make_unique<Context>(instance.inputContextManager());
                            context->focusIn();
                            context->setCapabilityFlags(fcitx::CapabilityFlag::Password);
                            context->key("Control_L"); context->key("Control+Alt_L");
                            break;
                        case 8:
                            require(server.starts == 2, "password or destroyed context opened mic");
                            context->key("Control+Alt+Alt_L", true);
                            context->setCapabilityFlags(fcitx::CapabilityFlags());
                            context->inputPanel().setClientPreedit(fcitx::Text("拼音"));
                            context->key("Control_L"); context->key("Control+Alt_L");
                            break;
                        case 9:
                            require(server.starts == 2, "hold interrupted existing composition");
                            context->key("Control+Alt+Alt_L", true);
                            context->inputPanel().reset();
                            server.delay = true;
                            context->key("Control_L"); context->key("Control+Alt_L");
                            // Next tick lands after threshold, before recording ack.
                            source->setNextInterval(350000); source->setOneShot(); return true;
                        case 10:
                            require(server.starts == 3, "delayed start missing");
                            context->key("Control+Alt+Alt_L", true);
                            server.delay = false;
                            break;
                        case 11:
                            require(server.cancels == 1, "release during startup did not cancel");
                            require(context->inputPanel().empty(), "startup release left stale UI");
                            result = 0; instance.exit(); return false;
                        }
                    } catch (const std::exception &error) {
                        std::cerr << "stage " << stage - 1 << ": " << error.what() << " starts=" << server.starts << " continuous=" << server.continuous << " status=" << context->inputPanel().auxUp().toString() << '\n';
                        instance.exit(); return false;
                    }
                    source->setNextInterval(450000); source->setOneShot(); return true;
                });
        });
        instance.exec();
        timer.reset(); context.reset();
        if (result != 0) return result;
    }
    fs::remove_all(root);
    std::cout << "Hold recording integration passed\n";
    return 0;
}

// Real Fcitx5 instance and input contexts; a local fixture replaces only ASR.
#include <fcitx-utils/event.h>
#include <fcitx-utils/eventdispatcher.h>
#include <fcitx-utils/eventloopinterface.h>
#include <fcitx/addonmanager.h>
#include <fcitx/addonfactory.h>
#include <fcitx/inputmethodengine.h>
#include <fcitx/event.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>
#include <fcitx/candidatelist.h>
#include <json-c/json.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <atomic>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
void require(bool ok, const char *message) {
    if (!ok) throw std::runtime_error(message);
}

class Context final : public fcitx::InputContext {
public:
    explicit Context(fcitx::InputContextManager &manager) : InputContext(manager, "voice-test") { created(); }
    ~Context() override { destroy(); }
    const char *frontend() const override { return "voice-test"; }
    void commitStringImpl(const std::string &text) override { commits.push_back(text); }
    void deleteSurroundingTextImpl(int, unsigned int) override {}
    void forwardKeyImpl(const fcitx::ForwardKeyEvent &) override {}
    void updatePreeditImpl() override {}
    bool key(const char *name) {
        fcitx::KeyEvent event(this, fcitx::Key(name));
        return keyEvent(event);
    }
    bool recording() const {
        auto text = inputPanel().auxUp().toString();
        return text.find("recording") != std::string::npos || text.find("录音中") != std::string::npos;
    }
    std::vector<std::string> commits;
};

// The real keyboard addon is statically linked into the fcitx5 executable,
// so a library-only harness supplies a pass-through engine for keyboard-us.
class Keyboard final : public fcitx::InputMethodEngine {
public:
    std::vector<fcitx::InputMethodEntry> listInputMethods() override {
        std::vector<fcitx::InputMethodEntry> entries;
        entries.emplace_back("keyboard-us", "Test keyboard", "en", "keyboard");
        return entries;
    }
    void keyEvent(const fcitx::InputMethodEntry &, fcitx::KeyEvent &) override {}
};
class KeyboardFactory final : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *) override { return new Keyboard; }
};

class Fixture {
public:
    explicit Fixture(const fs::path &path) {
        fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        require(fd >= 0, "fixture socket failed");
        sockaddr_un address{}; address.sun_family = AF_UNIX;
        std::strncpy(address.sun_path, path.c_str(), sizeof(address.sun_path)-1);
        require(bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0, "fixture bind failed");
        require(listen(fd, 4) == 0, "fixture listen failed");
        thread = std::thread([this] { run(); });
    }
    ~Fixture() { shutdown(fd, SHUT_RDWR); close(fd); thread.join(); }
    std::atomic<int> starts{0}, cancels{0};
private:
    static void sendLine(int client, const std::string &line) {
        std::string value = line + "\n";
        send(client, value.data(), value.size(), MSG_NOSIGNAL);
    }
    void run() {
        while (true) {
            int client = accept4(fd, nullptr, nullptr, SOCK_CLOEXEC);
            if (client < 0) return;
            timeval timeout{2, 0};
            setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
            sendLine(client, "{\"type\":\"ready\",\"protocol\":1}");
            std::string line; char ch;
            while (recv(client, &ch, 1, 0) == 1) {
                if (ch != '\n') { line += ch; continue; }
                auto *object = json_tokener_parse(line.c_str()); line.clear();
                if (!object) break;
                auto *type = json_object_object_get(object, "type");
                auto *identifier = json_object_object_get(object, "id");
                if (!type || !identifier) { json_object_put(object); break; }
                std::string kind = json_object_get_string(type);
                std::string id = json_object_to_json_string_ext(identifier, JSON_C_TO_STRING_PLAIN);
                json_object_put(object);
                if (kind == "start") {
                    ++starts;
                    // Fourth session pauses startup so cancellation/destruction is exercised.
                    if (starts != 4) sendLine(client, "{\"type\":\"recording\",\"id\":" + id + "}");
                } else if (kind == "stop") {
                    sendLine(client, "{\"type\":\"transcribing\",\"id\":" + id + "}");
                    sendLine(client, "{\"type\":\"result\",\"id\":" + id + ",\"text\":\"你好Ubuntu\"}");
                } else if (kind == "cancel") {
                    ++cancels;
                    // A late result after cancellation must never be committed.
                    sendLine(client, "{\"type\":\"result\",\"id\":" + id + ",\"text\":\"过期文字\"}");
                }
            }
            close(client);
        }
    }
    int fd;
    std::thread thread;
};

int main(int argc, char **argv) {
    require(argc == 2, "provide module path");
    char pattern[] = "/tmp/voice-it-XXXXXX";
    require(mkdtemp(pattern), "mkdtemp failed");
    fs::path root(pattern);
    fs::create_directories(root / "data/fcitx5/addon");
    fs::create_directories(root / "config");
    fs::create_directories(root / "fcitx5-voice");
    setenv("XDG_DATA_HOME", (root / "data").c_str(), 1);
    setenv("XDG_CONFIG_HOME", (root / "config").c_str(), 1);
    setenv("XDG_RUNTIME_DIR", root.c_str(), 1);
    auto library = fs::absolute(argv[1]); library.replace_extension();
    std::ofstream(root / "data/fcitx5/addon/voiceinput.conf")
        << "[Addon]\nName=Voice Test\nType=SharedLibrary\nCategory=Module\nOnDemand=False\nLibrary=" << library.string() << "\n";
    int result = 1;
    {
        Fixture server(root / "fcitx5-voice/service.sock");
        char name[] = "voice-integration", disable[] = "--disable=all", enable[] = "--enable=voiceinput,keyboard";
        char *arguments[] = {name, disable, enable};
        fcitx::Instance instance(3, arguments);
        KeyboardFactory keyboardFactory;
        fcitx::StaticAddonRegistry registry{{"keyboard", &keyboardFactory}};
        instance.addonManager().registerDefaultLoader(&registry);
        std::unique_ptr<Context> first, second;
        std::unique_ptr<fcitx::EventSourceTime> timer;
        int stage = 0;
        const auto deadline = fcitx::now(CLOCK_MONOTONIC) + 5'000'000;
        instance.eventDispatcher().schedule([&] {
            require(instance.addonManager().addon("voiceinput"), "absolute-path addon failed to load");
            first = std::make_unique<Context>(instance.inputContextManager());
            second = std::make_unique<Context>(instance.inputContextManager());
            first->focusIn();
            require(!first->key("a"), "ordinary key was swallowed while idle");
            require(first->key("Control+Alt+v"), "trigger was not accepted");
            timer = instance.eventLoop().addTimeEvent(CLOCK_MONOTONIC, fcitx::now(CLOCK_MONOTONIC), 0,
                [&](fcitx::EventSourceTime *source, uint64_t) {
                    try {
                        require(fcitx::now(CLOCK_MONOTONIC) < deadline, "integration timed out");
                        if (stage == 0 && first->recording()) {
                            first->key("Control+Alt+v"); stage = 1;
                        } else if (stage == 1 && first->inputPanel().candidateList()) {
                            first->key("BackSpace"); first->key("Return");
                            require(first->commits == std::vector<std::string>{"你好Ubunt"}, "preview/UTF8 edit/commit failed");
                            first->key("Control+Alt+v"); stage = 2;
                        } else if (stage == 2 && first->recording()) {
                            first->focusOut(); second->focusIn(); stage = 3;
                        } else if (stage == 3 && server.cancels >= 1) {
                            require(second->commits.empty(), "result committed into changed focus");
                            second->key("Control+Alt+v"); stage = 4;
                        } else if (stage == 4 && second->recording()) {
                            require(!second->key("a"), "normal typing was swallowed"); stage = 5;
                        } else if (stage == 5 && server.cancels >= 2) {
                            require(second->inputPanel().empty(), "normal typing left voice preview active");
                            require(second->commits.empty(), "cancelled text was committed");
                            second->setCapabilityFlags(fcitx::CapabilityFlag::Password);
                            second->key("Control+Alt+v"); stage = 6;
                        } else if (stage == 6) {
                            require(server.starts == 3, "password input opened microphone");
                            second->setCapabilityFlags(fcitx::CapabilityFlags());
                            second->inputPanel().setClientPreedit(fcitx::Text("拼音"));
                            second->key("Control+Alt+v"); stage = 7;
                        } else if (stage == 7) {
                            require(server.starts == 3, "existing composition opened microphone");
                            second->inputPanel().reset();
                            second->key("Control+Alt+v"); stage = 8;
                        } else if (stage == 8 && server.starts == 4) {
                            second->key("Control+Alt+v");
                            second.reset(); stage = 9;
                        } else if (stage == 9 && server.cancels >= 3) {
                            second = std::make_unique<Context>(instance.inputContextManager());
                            second->focusIn(); second->key("Control+Alt+v"); stage = 10;
                        } else if (stage == 10 && second->recording()) {
                            second->key("Escape"); stage = 11;
                        } else if (stage == 11 && server.cancels >= 4) {
                            require(second->commits.empty(), "startup cancellation left stale input");
                            result = 0; instance.exit(); return false;
                        }
                    } catch (const std::exception &error) {
                        std::cerr << "stage " << stage << ": " << error.what()
                                  << " starts=" << server.starts << " status=" << first->inputPanel().auxUp().toString()
                                  << " focus=" << first->hasFocus() << '\n';
                        instance.exit(); return false;
                    }
                    source->setNextInterval(10'000); source->setOneShot(); return true;
                });
        });
        instance.exec();
        timer.reset(); second.reset(); first.reset();
    }
    fs::remove_all(root);
    if (result == 0) std::cout << "Fcitx5 real-context integration passed\n";
    return result;
}

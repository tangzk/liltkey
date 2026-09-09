#include "session.h"

#include <cstdlib>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {

using voiceinput::Phase;
using voiceinput::Session;

void require(bool condition, std::string_view message) {
    if (!condition) {
        throw std::runtime_error(std::string(message));
    }
}

void test_utf8_backspace_removes_one_codepoint() {
    Session session;
    require(session.begin("session-1", 101), "session should start");
    require(session.handleLine(R"({"type":"ready","protocol":1})") ==
                std::optional<std::string>(
                    R"({"type":"start","id":"session-1"})" "\n"),
            "ready should produce the start request");
    require(session.handleLine(
                R"({"type":"recording","id":"session-1"})") ==
                std::nullopt,
            "recording acknowledgment should not produce a request");
    require(session.handleLine(
                R"({"type":"transcribing","id":"session-1"})") ==
                std::nullopt,
            "automatic recording limit may enter transcription");
    require(session.handleLine(
                R"({"type":"result","id":"session-1","text":"你好Ubuntu"})") ==
                std::nullopt,
            "result should not produce a request");
    require(session.phase() == Phase::Preview, "result should open preview");
    require(session.preview() == "你好Ubuntu", "preview text should match");

    require(session.backspace(101), "backspace should be handled in preview");
    require(session.preview() == "你好Ubunt",
            "backspace should remove one UTF-8 code point");
}

void test_stop_then_commit_requires_same_context() {
    Session session;
    require(session.begin("42", 1001), "session should start");
    session.handleLine(R"({"type":"ready","protocol":1})");
    session.handleLine(R"({"type":"recording","id":"42"})");

    require(session.toggle(1001) ==
                std::optional<std::string>(
                    R"({"type":"stop","id":"42"})" "\n"),
            "recording toggle should produce stop request");
    require(session.phase() == Phase::Stopping,
            "stop request should enter stopping phase");
    session.handleLine(R"({"type":"transcribing","id":"42"})");
    session.handleLine(
        R"({"type":"result","id":"42","text":"测试文本"})");

    require(!session.commit(2002).has_value(),
            "a different input context must never receive the text");
    require(session.phase() == Phase::Preview,
            "wrong-context enter must leave preview available");
    require(session.commit(1001) == std::optional<std::string>("测试文本"),
            "the originating input context may commit preview");
    require(session.phase() == Phase::Idle, "commit should end the session");
    require(!session.commit(1001).has_value(),
            "idle session must not commit twice");
}

void test_stale_and_invalid_phase_results_are_ignored() {
    Session session;
    require(session.begin("old", 7), "old session should start");
    session.handleLine(R"({"type":"ready","protocol":1})");
    session.handleLine(R"({"type":"recording","id":"old"})");
    require(session.cancel(7) ==
                std::optional<std::string>(
                    R"({"type":"cancel","id":"old"})" "\n"),
            "cancel should produce a cancel request");
    require(session.phase() == Phase::Idle, "cancel should immediately idle");

    require(session.begin("new", 8), "new session should start");
    session.handleLine(R"({"type":"ready","protocol":1})");
    session.handleLine(R"({"type":"recording","id":"new"})");
    session.handleLine(
        R"({"type":"result","id":"old","text":"旧结果"})");
    require(session.phase() == Phase::Recording,
            "stale result must not alter the new session");
    require(session.preview().empty(), "stale text must not reach preview");

    session.handleLine(
        R"({"type":"result","id":"new","text":"过早结果"})");
    require(session.phase() == Phase::Recording,
            "result is invalid before transcription starts");
    require(!session.commit(8).has_value(),
            "invalid-phase result must never become committable");
}

void test_malformed_and_oversized_messages_are_ignored() {
    Session session;
    require(session.begin("valid", 9), "session should start");

    require(!session.handleLine("not-json").has_value(),
            "malformed JSON must not produce output");
    require(session.phase() == Phase::Connecting,
            "malformed JSON must not change phase");
    require(!session.handleLine(R"({"type":"ready","protocol":2})")
                 .has_value(),
            "wrong protocol must be ignored");
    require(session.phase() == Phase::Connecting,
            "wrong protocol must not change phase");

    const std::string oversized(65537, 'x');
    require(!session.handleLine(oversized).has_value(),
            "oversized line must not produce output");
    require(session.phase() == Phase::Connecting,
            "oversized line must not change phase");
}

void test_sensitive_identifiers_and_text_limits() {
    Session session;
    require(!session.begin("", 1), "empty session id must be rejected");
    require(!session.begin(std::string(129, 'a'), 1),
            "overlong session id must be rejected");
    require(session.begin("ok", 1), "bounded session id should be accepted");
    session.handleLine(R"({"type":"ready","protocol":1})");
    session.handleLine(R"({"type":"recording","id":"ok"})");
    session.handleLine(R"({"type":"transcribing","id":"ok"})");
    session.handleLine(std::string(R"({"type":"result","id":"ok","text":")") +
                       std::string(8193, 'a') + R"("})");
    require(session.phase() == Phase::Transcribing,
            "oversized transcript must be ignored");
    require(session.preview().empty(),
            "oversized transcript must not become committable");
}

void test_connection_error_without_id_terminates_session() {
    Session session;
    require(session.begin("connect", 55), "session should start connecting");
    session.handleLine(R"({"type":"ready","protocol":1})");
    session.handleLine(
        R"({"type":"error","id":"stale","message":"busy"})");
    require(session.phase() == Phase::Starting,
            "stale connection error must not alter the current session");
    session.handleLine(R"({"type":"error","message":"busy"})");
    require(session.phase() == Phase::Idle,
            "connection-level error should terminate the session");
    require(session.takeError() == std::optional<std::string>("busy"),
            "connection-level error should be available to the UI");
}

void test_preview_rejects_control_characters() {
    Session session;
    require(session.begin("control", 77), "session should start");
    session.handleLine(R"({"type":"ready","protocol":1})");
    session.handleLine(R"({"type":"recording","id":"control"})");
    session.handleLine(R"({"type":"transcribing","id":"control"})");
    session.handleLine(
        R"({"type":"result","id":"control","text":"第一行\n第二行"})");
    require(session.phase() == Phase::Transcribing,
            "multiline transcript must not enter preview");
    require(!session.commit(77).has_value(),
            "control-bearing transcript must not be committable");
}

} // namespace

int main() {
    try {
        test_utf8_backspace_removes_one_codepoint();
        test_stop_then_commit_requires_same_context();
        test_stale_and_invalid_phase_results_are_ignored();
        test_malformed_and_oversized_messages_are_ignored();
        test_sensitive_identifiers_and_text_limits();
        test_connection_error_without_id_terminates_session();
        test_preview_rejects_control_characters();
    } catch (const std::exception &error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
    std::cout << "plugin state tests passed\n";
    return EXIT_SUCCESS;
}

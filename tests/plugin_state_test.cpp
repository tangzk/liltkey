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

void startStreaming(Session &session, std::string_view id,
                    std::uintptr_t context) {
    require(session.begin(std::string(id), context),
            "streaming session should start");
    require(session.handleLine(R"({"type":"ready","protocol":2})") ==
                std::optional<std::string>(
                    std::string(R"({"type":"start","id":")") +
                    std::string(id) + R"("})" "\n"),
            "protocol 2 ready should produce the start request");
    require(session.streaming(), "protocol 2 should select streaming mode");
    session.handleLine(std::string(R"({"type":"recording","id":")") +
                       std::string(id) + R"("})");
    require(session.phase() == Phase::Recording,
            "streaming session should enter recording");
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
    require(!session.handleLine(R"({"type":"ready","protocol":3})")
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


void test_streaming_partial_replaces_current_composition() {
    Session session;
    startStreaming(session, "stream", 201);

    session.handleLine(
        R"({"type":"partial","id":"stream","segment":1,"seq":1,"text":"你"})");
    require(session.preview() == "你", "first partial should be displayed");
    session.handleLine(
        R"({"type":"partial","id":"stream","segment":1,"seq":2,"text":"你好Ubuntu"})");
    require(session.preview() == "你好Ubuntu",
            "newer partial should replace the entire current segment");
    require(!session.takeCommit().has_value(),
            "a partial must never become a commit");
}

void test_streaming_final_commits_exactly_once_and_advances_segment() {
    Session session;
    startStreaming(session, "final", 202);

    session.handleLine(
        R"({"type":"partial","id":"final","segment":1,"seq":1,"text":"今天"})");
    session.handleLine(
        R"({"type":"final","id":"final","segment":1,"seq":2,"text":"今天下午"})");
    require(session.preview().empty(), "final should clear the composition");
    require(session.takeCommit() == std::optional<std::string>("今天下午"),
            "final should expose one pending commit");
    require(!session.takeCommit().has_value(),
            "a final must not be committed twice");

    session.handleLine(
        R"({"type":"final","id":"final","segment":1,"seq":3,"text":"重复"})");
    require(!session.takeCommit().has_value(),
            "duplicate final for an old segment must be ignored");
    session.handleLine(
        R"({"type":"partial","id":"final","segment":2,"seq":3,"text":"新句"})");
    require(session.preview() == "新句",
            "ignored old-segment event must not consume its sequence number");
    require(session.phase() == Phase::Recording,
            "a final sentence must not end a streaming session");
}

void test_streaming_rejects_stale_sequence_and_unexpected_segment() {
    Session session;
    startStreaming(session, "order", 203);

    session.handleLine(
        R"({"type":"partial","id":"order","segment":1,"seq":4,"text":"最新"})");
    session.handleLine(
        R"({"type":"partial","id":"order","segment":1,"seq":4,"text":"重复序号"})");
    session.handleLine(
        R"({"type":"partial","id":"order","segment":1,"seq":3,"text":"过期"})");
    session.handleLine(
        R"({"type":"partial","id":"order","segment":2,"seq":5,"text":"超前分句"})");
    require(session.preview() == "最新",
            "stale sequence and unexpected segment must not revise text");

    session.handleLine(
        R"({"type":"partial","id":"other","segment":1,"seq":5,"text":"旧会话"})");
    require(session.preview() == "最新",
            "a different session id must not revise text");
}

void test_streaming_empty_final_clears_and_advances() {
    Session session;
    startStreaming(session, "empty", 204);
    session.handleLine(
        R"({"type":"partial","id":"empty","segment":1,"seq":1,"text":"误识别"})");
    session.handleLine(
        R"({"type":"final","id":"empty","segment":1,"seq":2,"text":""})");

    require(session.preview().empty(), "empty final should clear preedit");
    require(session.takeCommit() == std::optional<std::string>(""),
            "empty final should still be delivered exactly once");
    session.handleLine(
        R"({"type":"partial","id":"empty","segment":2,"seq":3,"text":"第二句"})");
    require(session.preview() == "第二句",
            "empty final should advance to the next segment");
}

void test_streaming_accepts_stop_tail_and_finished_ends_session() {
    Session session;
    startStreaming(session, "tail", 205);
    require(session.toggle(205) ==
                std::optional<std::string>(
                    R"({"type":"stop","id":"tail"})" "\n"),
            "streaming stop should send the legacy-compatible stop frame");
    session.handleLine(
        R"({"type":"partial","id":"tail","segment":1,"seq":1,"text":"尾"})");
    require(session.preview() == "尾",
            "stopping should still accept a decoder revision");
    session.handleLine(R"({"type":"transcribing","id":"tail"})");
    session.handleLine(
        R"({"type":"final","id":"tail","segment":1,"seq":2,"text":"尾音"})");
    require(session.takeCommit() == std::optional<std::string>("尾音"),
            "stop flush final should be committable");
    session.handleLine(R"({"type":"finished","id":"tail"})");
    require(session.phase() == Phase::Idle,
            "finished should end the whole streaming session");
    require(!session.streaming(), "finished should clear streaming mode");
}

void test_streaming_rejects_invalid_event_fields() {
    Session session;
    startStreaming(session, "fields", 206);
    const std::string oversized(Session::MaxResultBytes + 1, 'x');

    session.handleLine(
        R"({"type":"partial","id":"fields","segment":"1","seq":1,"text":"bad"})");
    session.handleLine(
        R"({"type":"partial","id":"fields","segment":1,"seq":0,"text":"bad"})");
    session.handleLine(
        R"({"type":"partial","id":"fields","segment":1,"seq":1.5,"text":"bad"})");
    session.handleLine(
        R"({"type":"partial","id":"fields","segment":1,"seq":1,"text":7})");
    session.handleLine(
        R"({"type":"partial","id":"fields","segment":1,"seq":1,"text":"line\nbreak"})");
    session.handleLine(std::string(
                           R"({"type":"partial","id":"fields","segment":1,"seq":1,"text":")") +
                       oversized + R"("})");
    require(session.preview().empty(),
            "invalid streaming fields must not reach the composition");
    require(!session.takeCommit().has_value(),
            "invalid streaming fields must not create a commit");

    session.handleLine(
        R"({"type":"partial","id":"fields","segment":1,"seq":1,"text":"valid"})");
    require(session.preview() == "valid",
            "invalid events must not consume a valid sequence number");
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
        test_streaming_partial_replaces_current_composition();
        test_streaming_final_commits_exactly_once_and_advances_segment();
        test_streaming_rejects_stale_sequence_and_unexpected_segment();
        test_streaming_empty_final_clears_and_advances();
        test_streaming_accepts_stop_tail_and_finished_ends_session();
        test_streaming_rejects_invalid_event_fields();
    } catch (const std::exception &error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
    std::cout << "plugin state tests passed\n";
    return EXIT_SUCCESS;
}

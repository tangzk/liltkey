#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace voiceinput {

enum class Phase {
    Idle,
    Connecting,
    Starting,
    Recording,
    Stopping,
    Transcribing,
    Preview,
};

class Session {
public:
    static constexpr std::size_t MaxLineBytes = 65536;
    static constexpr std::size_t MaxIdBytes = 128;
    static constexpr std::size_t MaxResultBytes = 8192;

    bool begin(std::string id, std::uintptr_t context, bool continuous = false);
    std::optional<std::string> handleLine(std::string_view line);
    std::optional<std::string> toggle(std::uintptr_t context);
    std::optional<std::string> cancel(std::uintptr_t context);
    void abandon();

    bool backspace(std::uintptr_t context);
    std::optional<std::string> commit(std::uintptr_t context);

    Phase phase() const { return phase_; }
    std::uintptr_t context() const { return context_; }
    const std::string &id() const { return id_; }
    const std::string &preview() const { return preview_; }
    bool streaming() const { return streaming_; }
    bool activeFor(std::uintptr_t context) const;
    std::optional<std::string> takeCommit();
    std::optional<std::string> takeError();

private:
    std::string request(std::string_view type) const;
    void reset();

    Phase phase_ = Phase::Idle;
    std::uintptr_t context_ = 0;
    std::string id_;
    std::string preview_;
    bool streaming_ = false;
    bool continuous_ = false;
    std::int64_t expectedSegment_ = 1;
    std::int64_t lastSequence_ = 0;
    std::optional<std::string> pendingCommit_;
    std::optional<std::string> error_;
};

bool validUtf8(std::string_view text);
bool eraseLastUtf8(std::string &text);

} // namespace voiceinput

#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace voiceinput {

struct FeedResult {
    std::vector<std::string> lines;
    bool overflow = false;
};

class LineBuffer {
public:
    explicit LineBuffer(std::size_t limit) : limit_(limit) {}

    FeedResult feed(std::string_view chunk) {
        FeedResult result;
        for (const char byte : chunk) {
            if (discarding_) {
                if (byte == '\n') {
                    discarding_ = false;
                }
                continue;
            }
            if (byte == '\n') {
                result.lines.push_back(std::move(buffer_));
                buffer_.clear();
                continue;
            }
            if (buffer_.size() == limit_) {
                buffer_.clear();
                discarding_ = true;
                result.overflow = true;
                continue;
            }
            buffer_.push_back(byte);
        }
        return result;
    }

    void clear() {
        buffer_.clear();
        discarding_ = false;
    }

private:
    std::size_t limit_;
    std::string buffer_;
    bool discarding_ = false;
};

} // namespace voiceinput

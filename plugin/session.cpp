#include "session.h"

#include <json-c/json.h>

#include <cstddef>
#include <memory>
#include <utility>

namespace voiceinput {
namespace {

using JsonPtr = std::unique_ptr<json_object, decltype(&json_object_put)>;

JsonPtr parseObject(std::string_view line) {
    if (line.empty() || line.size() >= Session::MaxLineBytes ||
        !validUtf8(line)) {
        return JsonPtr(nullptr, json_object_put);
    }
    std::unique_ptr<json_tokener, decltype(&json_tokener_free)> tokener(
        json_tokener_new(), json_tokener_free);
    if (!tokener) {
        return JsonPtr(nullptr, json_object_put);
    }
    json_tokener_set_flags(tokener.get(), JSON_TOKENER_VALIDATE_UTF8);
    const std::string terminated(line);
    json_object *raw = json_tokener_parse_ex(
        tokener.get(), terminated.c_str(), terminated.size() + 1);
    if (json_tokener_get_error(tokener.get()) != json_tokener_success ||
        tokener->char_offset != static_cast<int>(line.size()) || !raw ||
        json_object_get_type(raw) != json_type_object) {
        if (raw) {
            json_object_put(raw);
        }
        return JsonPtr(nullptr, json_object_put);
    }
    return JsonPtr(raw, json_object_put);
}

std::optional<std::string_view> stringField(json_object *object,
                                            const char *name) {
    json_object *value = nullptr;
    if (!json_object_object_get_ex(object, name, &value) ||
        json_object_get_type(value) != json_type_string) {
        return std::nullopt;
    }
    return std::string_view(json_object_get_string(value),
                            json_object_get_string_len(value));
}

std::optional<std::int64_t> integerField(json_object *object,
                                         const char *name) {
    json_object *value = nullptr;
    if (!json_object_object_get_ex(object, name, &value) ||
        json_object_get_type(value) != json_type_int) {
        return std::nullopt;
    }
    return json_object_get_int64(value);
}

bool hasControlCharacters(std::string_view text) {
    for (const unsigned char byte : text) {
        if (byte < 0x20 || byte == 0x7f) {
            return true;
        }
    }
    return false;
}

} // namespace

bool validUtf8(std::string_view text) {
    std::size_t i = 0;
    while (i < text.size()) {
        const auto first = static_cast<unsigned char>(text[i]);
        std::size_t count = 0;
        std::uint32_t codepoint = 0;
        if (first <= 0x7f) {
            count = 1;
            codepoint = first;
        } else if (first >= 0xc2 && first <= 0xdf) {
            count = 2;
            codepoint = first & 0x1f;
        } else if (first >= 0xe0 && first <= 0xef) {
            count = 3;
            codepoint = first & 0x0f;
        } else if (first >= 0xf0 && first <= 0xf4) {
            count = 4;
            codepoint = first & 0x07;
        } else {
            return false;
        }
        if (i + count > text.size()) {
            return false;
        }
        for (std::size_t offset = 1; offset < count; ++offset) {
            const auto byte = static_cast<unsigned char>(text[i + offset]);
            if ((byte & 0xc0) != 0x80) {
                return false;
            }
            codepoint = (codepoint << 6) | (byte & 0x3f);
        }
        if ((count == 3 && codepoint < 0x800) ||
            (count == 4 && codepoint < 0x10000) || codepoint > 0x10ffff ||
            (codepoint >= 0xd800 && codepoint <= 0xdfff)) {
            return false;
        }
        i += count;
    }
    return true;
}

bool eraseLastUtf8(std::string &text) {
    if (text.empty() || !validUtf8(text)) {
        return false;
    }
    std::size_t start = text.size() - 1;
    while (start > 0 &&
           (static_cast<unsigned char>(text[start]) & 0xc0) == 0x80) {
        --start;
    }
    text.erase(start);
    return true;
}

bool Session::begin(std::string id, std::uintptr_t context, bool continuous) {
    if (phase_ != Phase::Idle || context == 0 || id.empty() ||
        id.size() > MaxIdBytes || !validUtf8(id)) {
        return false;
    }
    continuous_ = continuous;
    id_ = std::move(id);
    context_ = context;
    preview_.clear();
    streaming_ = false;
    expectedSegment_ = 1;
    lastSequence_ = 0;
    pendingCommit_.reset();
    error_.reset();
    phase_ = Phase::Connecting;
    return true;
}

std::string Session::request(std::string_view type) const {
    JsonPtr object(json_object_new_object(), json_object_put);
    json_object_object_add(object.get(), "type",
                           json_object_new_string_len(type.data(), type.size()));
    json_object_object_add(object.get(), "id",
                           json_object_new_string_len(id_.data(), id_.size()));
    if (type == "start" && continuous_) {
        json_object_object_add(object.get(), "continuous", json_object_new_boolean(true));
    }
    std::string result = json_object_to_json_string_ext(
        object.get(), JSON_C_TO_STRING_PLAIN);
    result.push_back('\n');
    return result;
}

std::optional<std::string> Session::handleLine(std::string_view line) {
    auto object = parseObject(line);
    if (!object) {
        return std::nullopt;
    }
    const auto type = stringField(object.get(), "type");
    if (!type) {
        return std::nullopt;
    }

    if (*type == "ready") {
        const auto protocol = integerField(object.get(), "protocol");
        if (phase_ == Phase::Connecting && protocol &&
            (*protocol == 1 || *protocol == 2)) {
            streaming_ = *protocol == 2;
            phase_ = Phase::Starting;
            return request("start");
        }
        return std::nullopt;
    }

    if ((*type == "error" || *type == "busy") &&
        (phase_ == Phase::Connecting || phase_ == Phase::Starting)) {
        json_object *rawId = nullptr;
        if (json_object_object_get_ex(object.get(), "id", &rawId)) {
            if (json_object_get_type(rawId) != json_type_string) {
                return std::nullopt;
            }
            const auto connectionId = stringField(object.get(), "id");
            if (!connectionId || *connectionId != id_) {
                return std::nullopt;
            }
        }
        const auto message = stringField(object.get(), "message");
        if (*type == "busy") {
            error_ = "语音服务正忙";
            reset();
        } else if (message && !message->empty() &&
                   message->size() <= MaxLineBytes && validUtf8(*message) &&
                   !hasControlCharacters(*message)) {
            error_ = std::string(*message);
            reset();
        }
        return std::nullopt;
    }

    const auto eventId = stringField(object.get(), "id");
    if (!eventId || eventId->empty() || eventId->size() > MaxIdBytes ||
        *eventId != id_ || phase_ == Phase::Idle) {
        return std::nullopt;
    }

    if (*type == "recording" && phase_ == Phase::Starting) {
        phase_ = Phase::Recording;
    } else if (*type == "transcribing" &&
               (phase_ == Phase::Recording || phase_ == Phase::Stopping)) {
        phase_ = Phase::Transcribing;
    } else if (*type == "result" && !streaming_ &&
               phase_ == Phase::Transcribing) {
        const auto text = stringField(object.get(), "text");
        if (text && !text->empty() && text->size() <= MaxResultBytes &&
            validUtf8(*text) && !hasControlCharacters(*text)) {
            preview_.assign(*text);
            phase_ = Phase::Preview;
        }
    } else if ((*type == "partial" || *type == "final") && streaming_ &&
               (phase_ == Phase::Recording || phase_ == Phase::Stopping ||
                phase_ == Phase::Transcribing)) {
        const auto segment = integerField(object.get(), "segment");
        const auto sequence = integerField(object.get(), "seq");
        const auto text = stringField(object.get(), "text");
        if (!segment || !sequence || !text ||
            *segment != expectedSegment_ || *sequence <= 0 ||
            *sequence <= lastSequence_ || text->size() > MaxResultBytes ||
            !validUtf8(*text) || hasControlCharacters(*text)) {
            return std::nullopt;
        }
        lastSequence_ = *sequence;
        if (*type == "partial") {
            preview_.assign(*text);
        } else {
            pendingCommit_ = std::string(*text);
            preview_.clear();
            ++expectedSegment_;
        }
    } else if (*type == "finished" && streaming_ &&
               (phase_ == Phase::Recording || phase_ == Phase::Stopping ||
                phase_ == Phase::Transcribing)) {
        reset();
    } else if (*type == "cancelled" && phase_ != Phase::Preview) {
        reset();
    } else if (*type == "error" && phase_ != Phase::Preview) {
        const auto message = stringField(object.get(), "message");
        if (message && !message->empty() && message->size() <= MaxLineBytes &&
            validUtf8(*message) && !hasControlCharacters(*message)) {
            error_ = std::string(*message);
            reset();
        }
    }
    return std::nullopt;
}

std::optional<std::string> Session::toggle(std::uintptr_t context) {
    if (!activeFor(context)) {
        return std::nullopt;
    }
    if (phase_ == Phase::Recording) {
        phase_ = Phase::Stopping;
        return request("stop");
    }
    if (phase_ == Phase::Connecting) {
        reset();
        return std::nullopt;
    }
    if (phase_ == Phase::Starting) {
        const auto result = request("cancel");
        reset();
        return result;
    }
    return std::nullopt;
}

std::optional<std::string> Session::cancel(std::uintptr_t context) {
    if (!activeFor(context)) {
        return std::nullopt;
    }
    std::optional<std::string> result;
    if (phase_ == Phase::Starting || phase_ == Phase::Recording ||
        phase_ == Phase::Stopping || phase_ == Phase::Transcribing) {
        result = request("cancel");
    }
    reset();
    return result;
}

void Session::abandon() { reset(); }

bool Session::backspace(std::uintptr_t context) {
    if (phase_ != Phase::Preview || context != context_) {
        return false;
    }
    eraseLastUtf8(preview_);
    return true;
}

std::optional<std::string> Session::commit(std::uintptr_t context) {
    if (phase_ != Phase::Preview || context != context_) {
        return std::nullopt;
    }
    std::string text = std::move(preview_);
    reset();
    return text;
}

bool Session::activeFor(std::uintptr_t context) const {
    return phase_ != Phase::Idle && context != 0 && context == context_;
}

std::optional<std::string> Session::takeError() {
    return std::exchange(error_, std::nullopt);
}

std::optional<std::string> Session::takeCommit() {
    return std::exchange(pendingCommit_, std::nullopt);
}

void Session::reset() {
    phase_ = Phase::Idle;
    context_ = 0;
    continuous_ = false;
    id_.clear();
    preview_.clear();
    streaming_ = false;
    expectedSegment_ = 1;
    lastSequence_ = 0;
    pendingCommit_.reset();
}

} // namespace voiceinput

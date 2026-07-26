#pragma once

#include <Geode/Geode.hpp>
#include <Geode/binding/PlayLayer.hpp>
#include <Geode/binding/PlayerObject.hpp>

#include <algorithm>
#include <array>
#include <cfloat>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>

namespace gati {

constexpr int kNumRays = 5;
constexpr double kRayOffsets[kNumRays] = {-30.0, -15.0, 0.0, 15.0, 30.0};
constexpr double kScanDistance = 300.0;

struct BridgeState {
    double xPos = 0.0;
    double yPos = 0.0;
    double xVel = 0.0;
    double yVel = 0.0;
    double rotation = 0.0;
    bool isGrounded = false;
    bool isDead = false;
    bool hasWon = false;
    double dt = 0.0;
    std::array<double, kNumRays> rayDist{};
};

struct ActionCommand {
    bool jump = false;
    bool restart = false;
    bool pause = false;
};

inline std::string toJson(const BridgeState& state) {
    std::ostringstream stream;
    stream.setf(std::ios::fixed, std::ios::floatfield);
    stream.precision(3);
    stream
        << '{'
        << "\"xPos\":" << state.xPos << ','
        << "\"yPos\":" << state.yPos << ','
        << "\"xVel\":" << state.xVel << ','
        << "\"yVel\":" << state.yVel << ','
        << "\"rotation\":" << state.rotation << ','
        << "\"isGrounded\":" << (state.isGrounded ? "true" : "false") << ','
        << "\"isDead\":" << (state.isDead ? "true" : "false") << ','
        << "\"hasWon\":" << (state.hasWon ? "true" : "false") << ','
        << "\"dt\":" << state.dt << ','
        << "\"rays\":[";
    for (int i = 0; i < kNumRays; ++i) {
        if (i > 0) stream << ',';
        stream << state.rayDist[i];
    }
    stream << "]}";
    return stream.str();
}

inline BridgeState extractState(::PlayLayer* playLayer, float dt) {
    BridgeState state;
    state.dt = dt;

    for (int i = 0; i < kNumRays; ++i) {
        state.rayDist[i] = kScanDistance;
    }

    if (playLayer == nullptr || playLayer->m_player1 == nullptr) {
        return state;
    }

    auto* player = playLayer->m_player1;
    const float playerX = player->m_position.x;
    const float playerY = player->m_position.y;

    state.xPos = static_cast<double>(playerX);
    state.yPos = static_cast<double>(playerY);
    state.xVel = static_cast<double>(player->m_playerSpeed);
    state.yVel = player->m_yVelocity;
    state.rotation = static_cast<double>(player->getRotation());
    state.isGrounded = player->m_isOnGround;
    state.isDead = player->m_isDead;
    state.hasWon = playLayer->m_levelEndAnimationStarted;

    auto* objects = playLayer->m_objects;
    if (objects == nullptr) {
        return state;
    }

    const unsigned int count = objects->count();
    for (unsigned int i = 0; i < count; ++i) {
        auto* obj = static_cast<::GameObject*>(objects->objectAtIndex(i));
        if (obj == nullptr || obj->m_isDisabled || obj->m_isInvisible) {
            continue;
        }

        const double objX = obj->m_positionX;
        const double dx = objX - playerX;
        if (dx <= 0.0 || dx >= kScanDistance) {
            continue;
        }

        const double objY = obj->m_positionY;
        const double halfW = (obj->m_width > 0.0) ? obj->m_width * 0.5 : 15.0;
        const double halfH = (obj->m_height > 0.0) ? obj->m_height * 0.5 : 15.0;

        for (int r = 0; r < kNumRays; ++r) {
            const double rayY = playerY + kRayOffsets[r];
            if (rayY >= objY - halfH && rayY <= objY + halfH) {
                const double edgeDist = dx - halfW;
                if (edgeDist > 0.0 && edgeDist < state.rayDist[r]) {
                    state.rayDist[r] = edgeDist;
                }
            }
        }
    }

    return state;
}

inline std::optional<ActionCommand> parseActionCommand(std::string_view payload) {
    ActionCommand command;
    bool hasMeaningfulField = false;

    const auto contains = [&](std::string_view token) {
        return payload.find(token) != std::string_view::npos;
    };

    if (contains("\"restart\":true") || contains("\"reset\":true") || contains("\"command\":\"reset\"") || contains("\"command\":\"restart\"")) {
        command.restart = true;
        hasMeaningfulField = true;
    }

    if (contains("\"pause\":true") || contains("\"command\":\"pause\"")) {
        command.pause = true;
        hasMeaningfulField = true;
    }

    if (contains("\"action\":1") || contains("\"jump\":true")) {
        command.jump = true;
        hasMeaningfulField = true;
    }

    if (!hasMeaningfulField && (contains("\"action\":0") || contains("\"jump\":false"))) {
        hasMeaningfulField = true;
    }

    if (!hasMeaningfulField) {
        return std::nullopt;
    }

    return command;
}

} // namespace gati

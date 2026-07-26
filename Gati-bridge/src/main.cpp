#define WIN32_LEAN_AND_MEAN

#include <winsock2.h>
#include <ws2tcpip.h>

#include <Geode/Geode.hpp>
#include <Geode/Enums.hpp>

using namespace geode::prelude;

#include <Geode/modify/MenuLayer.hpp>
#include <Geode/modify/PlayLayer.hpp>

#include "SocketServer.hpp"
#include "StateExtractor.hpp"

namespace {

constexpr int kFrameSkip = 4;
constexpr int kResetGraceFrames = 5;

class BridgeController {
public:
    static BridgeController& shared() {
        static BridgeController controller;
        return controller;
    }

    void tick(PlayLayer* playLayer, float dt) {
        if (!m_server.start()) {
            return;
        }

        m_frameCount++;

        m_server.syncRead();

        if (auto action = m_server.consumeAction()) {
            m_lastAction = *action;
            m_graceFrames = 0;

            if (action->restart) {
                log::debug("Gati bridge received restart command");
                playLayer->resetLevel();
                m_graceFrames = kResetGraceFrames;
                m_lastAction = {};
            }

            if (m_lastAction.jump) {
                playLayer->m_player1->pushButton(PlayerButton::Jump);
            } else {
                playLayer->m_player1->releaseButton(PlayerButton::Jump);
            }
        }

        if ((m_frameCount % kFrameSkip) != 0) {
            return;
        }

        auto state = gati::extractState(playLayer, dt);

        if (m_graceFrames > 0) {
            m_graceFrames--;
            state.isDead = false;
            state.hasWon = false;
        }

        m_server.syncSend(state);
    }

private:
    gati::SocketServer m_server;
    gati::ActionCommand m_lastAction{};
    int m_frameCount = 0;
    int m_graceFrames = 0;
};

} // namespace

class $modify(MyMenuLayer, MenuLayer) {
    bool init() {
        if (!MenuLayer::init()) {
            return false;
        }

        log::debug("Hello from Gati-bridge. MenuLayer has {} children.", this->getChildrenCount());

        auto myButton = CCMenuItemSpriteExtra::create(
            CCSprite::createWithSpriteFrameName("GJ_likeBtn_001.png"),
            this,
            menu_selector(MyMenuLayer::onMyButton)
        );

        auto menu = this->getChildByID("bottom-menu");
        if (menu != nullptr) {
            menu->addChild(myButton);
            myButton->setID("gati-button"_spr);
            menu->updateLayout();
        }

        return true;
    }

    void onMyButton(CCObject*) {
        FLAlertLayer::create("Gati-bridge", "The bridge scaffolding is loaded.", "OK")->show();
    }
};

class $modify(MyPlayLayer, PlayLayer) {
    void postUpdate(float dt) {
        PlayLayer::postUpdate(dt);
        BridgeController::shared().tick(this, dt);
    }
};

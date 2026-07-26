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

        bool didReset = false;

        // 1. Read any pending commands from the socket
        m_server.syncRead();

        // 2. Process the action (if any) BEFORE extracting state
        if (auto action = m_server.consumeAction()) {
            m_lastAction = *action;
            if (action->restart) {
                log::debug("Gati bridge received restart command");
				playLayer->resetLevel();
                didReset = true;
            }
            if (action->jump) {
                log::debug("Gati bridge received jump command");
                playLayer->m_player1->pushButton(PlayerButton::Jump);
            } else {
                playLayer->m_player1->releaseButton(PlayerButton::Jump);
            }
        }

        // 3. Now extract state (after actions applied) and send it
		auto state = gati::extractState(playLayer, dt);
        if (didReset) {
            state.isDead = false;
            state.hasWon = false;
        }
		m_server.syncSend(state);
    }

private:
    gati::SocketServer m_server;
    gati::ActionCommand m_lastAction{};
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
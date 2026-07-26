#pragma once

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

#include "StateExtractor.hpp"

#include <cstddef>
#include <mutex>
#include <optional>
#include <string>
#include <utility>

namespace gati {

class SocketServer {
public:
    SocketServer(std::string host = "127.0.0.1", unsigned short port = 6969)
        : m_host(std::move(host))
        , m_port(port) {}

    ~SocketServer() {
        stop();
    }

    bool start() {
        std::scoped_lock lock(m_mutex);

        if (m_running) {
            return true;
        }

#ifdef _WIN32
        if (!initializeWinsock()) {
            return false;
        }

        m_serverSocket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (m_serverSocket == INVALID_SOCKET) {
            return false;
        }

        setNonBlocking(m_serverSocket);

        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(m_port);
        if (::inet_pton(AF_INET, m_host.c_str(), &address.sin_addr) != 1) {
            closeSocket(m_serverSocket);
            m_serverSocket = INVALID_SOCKET;
            return false;
        }

        constexpr int reuseEnabled = 1;
        ::setsockopt(m_serverSocket, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&reuseEnabled), sizeof(reuseEnabled));

        if (::bind(m_serverSocket, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == SOCKET_ERROR) {
            closeSocket(m_serverSocket);
            m_serverSocket = INVALID_SOCKET;
            return false;
        }

        if (::listen(m_serverSocket, SOMAXCONN) == SOCKET_ERROR) {
            closeSocket(m_serverSocket);
            m_serverSocket = INVALID_SOCKET;
            return false;
        }

        m_running = true;
        geode::log::info("Gati bridge listening on {}:{}", m_host, m_port);
        return true;
#else
        m_running = true;
        return true;
#endif
    }

    void stop() {
        std::scoped_lock lock(m_mutex);
        if (!m_running) {
            return;
        }

#ifdef _WIN32
        closeSocket(m_clientSocket);
        closeSocket(m_serverSocket);
        m_clientSocket = INVALID_SOCKET;
        m_serverSocket = INVALID_SOCKET;
#endif
        m_running = false;
        m_receiveBuffer.clear();
        m_pendingAction.reset();
    }

    void step(const BridgeState& state) {
        if (!m_running && !start()) {
            return;
        }

        std::scoped_lock lock(m_mutex);
        m_lastState = state;

#ifdef _WIN32
        acceptClientIfNeeded();
        if (m_clientSocket == INVALID_SOCKET) {
            return;
        }

        readClientCommands();
        sendState(state);
#endif
    }

    void syncRead() {
        if (!m_running) {
            return;
        }

        std::scoped_lock lock(m_mutex);

#ifdef _WIN32
        acceptClientIfNeeded();
        if (m_clientSocket == INVALID_SOCKET) {
            return;
        }

        readClientCommands();
#endif
    }

    void syncSend(const BridgeState& state) {
        if (!m_running) {
            return;
        }

        std::scoped_lock lock(m_mutex);
        m_lastState = state;

#ifdef _WIN32
        if (m_clientSocket == INVALID_SOCKET) {
            return;
        }

        sendState(state);
#endif
    }

    std::optional<ActionCommand> consumeAction() {
        std::scoped_lock lock(m_mutex);
        auto action = m_pendingAction;
        m_pendingAction.reset();
        return action;
    }

private:
#ifdef _WIN32
    static bool initializeWinsock() {
        static bool initialized = false;
        static bool success = false;
        if (initialized) {
            return success;
        }

        WSADATA data{};
        success = (::WSAStartup(MAKEWORD(2, 2), &data) == 0);
        initialized = true;
        return success;
    }

    static void setNonBlocking(SOCKET socketHandle) {
        u_long mode = 1;
        ::ioctlsocket(socketHandle, FIONBIO, &mode);
    }

    static void closeSocket(SOCKET socketHandle) {
        if (socketHandle != INVALID_SOCKET) {
            ::closesocket(socketHandle);
        }
    }

    void acceptClientIfNeeded() {
        if (m_clientSocket != INVALID_SOCKET) {
            return;
        }

        sockaddr_in clientAddress{};
        int length = sizeof(clientAddress);
        SOCKET acceptedSocket = ::accept(m_serverSocket, reinterpret_cast<sockaddr*>(&clientAddress), &length);
        if (acceptedSocket == INVALID_SOCKET) {
            return;
        }

        setNonBlocking(acceptedSocket);
        m_clientSocket = acceptedSocket;
        m_receiveBuffer.clear();
        geode::log::info("Gati bridge client connected");
    }

    void sendState(const BridgeState& state) {
        const std::string payload = toJson(state) + "\n";
        const int sent = ::send(m_clientSocket, payload.c_str(), static_cast<int>(payload.size()), 0);
        if (sent == SOCKET_ERROR) {
            const int error = ::WSAGetLastError();
            if (error != WSAEWOULDBLOCK) {
                closeSocket(m_clientSocket);
                m_clientSocket = INVALID_SOCKET;
            }
        }
    }

    void readClientCommands() {
        char buffer[1024];
        while (true) {
            const int received = ::recv(m_clientSocket, buffer, static_cast<int>(sizeof(buffer)), 0);
            if (received > 0) {
                m_receiveBuffer.append(buffer, buffer + received);
                continue;
            }

            if (received == 0) {
                closeSocket(m_clientSocket);
                m_clientSocket = INVALID_SOCKET;
                return;
            }

            const int error = ::WSAGetLastError();
            if (error != WSAEWOULDBLOCK) {
                closeSocket(m_clientSocket);
                m_clientSocket = INVALID_SOCKET;
            }
            break;
        }

        const std::size_t newlinePosition = m_receiveBuffer.find('\n');
        if (newlinePosition == std::string::npos) {
            return;
        }

        const std::string message = m_receiveBuffer.substr(0, newlinePosition);
        m_receiveBuffer.erase(0, newlinePosition + 1);

        if (auto action = parseActionCommand(message)) {
            m_pendingAction = action;
        }
    }

    SOCKET m_serverSocket = INVALID_SOCKET;
    SOCKET m_clientSocket = INVALID_SOCKET;
#endif

    std::string m_host;
    unsigned short m_port = 6969;
    bool m_running = false;
    BridgeState m_lastState{};
    std::string m_receiveBuffer;
    std::optional<ActionCommand> m_pendingAction;
    mutable std::mutex m_mutex;
};

} // namespace gati

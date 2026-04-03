#pragma once

#include <winsock2.h>
#include <ws2tcpip.h>

#include <webots/Robot.hpp>

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace webots_mcp_kit {

struct CameraFrame {
  std::string name;
  const unsigned char *image;
  int width;
  int height;
};

class ControllerAgent {
public:
  static ControllerAgent from_robot(webots::Robot *robot, const std::string &default_camera) {
    return ControllerAgent(robot, default_camera);
  }

  ControllerAgent(const ControllerAgent &) = delete;
  ControllerAgent &operator=(const ControllerAgent &) = delete;

  ControllerAgent(ControllerAgent &&other) noexcept { move_from(std::move(other)); }

  ControllerAgent &operator=(ControllerAgent &&other) noexcept {
    if (this != &other) {
      close_socket();
      move_from(std::move(other));
    }
    return *this;
  }

  ~ControllerAgent() { close_socket(); }

  std::optional<std::pair<double, double>> begin_step() {
    drain_messages();
    if (paused_)
      return std::pair<double, double>{0.0, 0.0};
    if (manual_override_active_) {
      auto override = std::pair<double, double>{manual_left_, manual_right_};
      manual_remaining_steps_ -= 1;
      if (manual_remaining_steps_ <= 0)
        manual_override_active_ = false;
      return override;
    }
    return std::nullopt;
  }

  void report_step(const std::map<std::string, double> &sensors,
                   const std::map<std::string, double> &metrics,
                   const std::map<std::string, double> &actuators,
                   const std::vector<CameraFrame> &camera_frames = {}) {
    handle_pending_captures(camera_frames);
    step_index_ += 1;
    std::ostringstream payload;
    payload << "{\"kind\":\"telemetry\",\"role\":\"agent\",\"name\":\"" << escape(robot_->getName()) << "\",";
    payload << "\"devices\":[],";
    payload << "\"state\":{\"robot_time\":" << robot_->getTime() << ",\"step_index\":" << step_index_
            << ",\"basic_time_step\":" << static_cast<int>(robot_->getBasicTimeStep()) << "},";
    payload << "\"sensors\":" << map_to_json(sensors) << ",";
    payload << "\"metrics\":" << map_to_json(metrics) << ",";
    payload << "\"actuators\":" << map_to_json(actuators) << ",";
    payload << "\"meta\":{\"paused\":" << (paused_ ? "true" : "false") << ",\"default_camera\":\"" << escape(default_camera_)
            << "\"}}\n";
    send_line(payload.str());
  }

private:
  struct PendingCapture {
    std::string request_id;
    std::string camera;
    std::string path;
  };

  explicit ControllerAgent(webots::Robot *robot, std::string default_camera)
      : robot_(robot), default_camera_(std::move(default_camera)) {
    connect_socket();
    register_runtime();
  }

  void move_from(ControllerAgent &&other) noexcept {
    robot_ = other.robot_;
    default_camera_ = std::move(other.default_camera_);
    socket_ = other.socket_;
    paused_ = other.paused_;
    manual_override_active_ = other.manual_override_active_;
    manual_left_ = other.manual_left_;
    manual_right_ = other.manual_right_;
    manual_remaining_steps_ = other.manual_remaining_steps_;
    step_index_ = other.step_index_;
    recv_buffer_ = std::move(other.recv_buffer_);
    pending_captures_ = std::move(other.pending_captures_);
    other.socket_ = INVALID_SOCKET;
  }

  void connect_socket() {
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0)
      throw std::runtime_error("WSAStartup failed.");

    const char *host = std::getenv("WEBOTS_MCP_HOST");
    const char *port = std::getenv("WEBOTS_MCP_PORT");
    if (host == nullptr || port == nullptr)
      throw std::runtime_error("WEBOTS_MCP_HOST/WEBOTS_MCP_PORT must be set.");

    socket_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socket_ == INVALID_SOCKET)
      throw std::runtime_error("Unable to create runtime socket.");

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(static_cast<u_short>(std::stoi(port)));
    if (inet_pton(AF_INET, host, &address.sin_addr) != 1)
      throw std::runtime_error("Unable to parse WEBOTS_MCP_HOST.");

    if (connect(socket_, reinterpret_cast<sockaddr *>(&address), sizeof(address)) != 0)
      throw std::runtime_error("Unable to connect to the runtime socket.");

    u_long nonblocking = 1;
    ioctlsocket(socket_, FIONBIO, &nonblocking);
  }

  void register_runtime() {
    std::ostringstream payload;
    payload << "{\"kind\":\"runtime_register\",\"role\":\"agent\",\"name\":\"" << escape(robot_->getName())
            << "\",\"meta\":{\"default_camera\":\"" << escape(default_camera_) << "\"}}\n";
    send_line(payload.str());
  }

  void close_socket() {
    if (socket_ != INVALID_SOCKET) {
      closesocket(socket_);
      socket_ = INVALID_SOCKET;
      WSACleanup();
    }
  }

  void drain_messages() {
    if (socket_ == INVALID_SOCKET)
      return;
    char buffer[4096];
    while (true) {
      int bytes = recv(socket_, buffer, sizeof(buffer), 0);
      if (bytes > 0) {
        recv_buffer_.append(buffer, bytes);
      } else if (bytes == 0) {
        break;
      } else {
        int error = WSAGetLastError();
        if (error == WSAEWOULDBLOCK)
          break;
        throw std::runtime_error("Runtime socket receive failed.");
      }
    }

    size_t newline = recv_buffer_.find('\n');
    while (newline != std::string::npos) {
      std::string line = recv_buffer_.substr(0, newline);
      recv_buffer_.erase(0, newline + 1);
      handle_message(line);
      newline = recv_buffer_.find('\n');
    }
  }

  void handle_message(const std::string &line) {
    if (extract_string(line, "kind") != "command")
      return;
    const std::string request_id = extract_string(line, "request_id");
    const std::string action = extract_string(line, "action");
    if (action == "set_motor_velocity") {
      manual_left_ = extract_number(line, "left", 0.0);
      manual_right_ = extract_number(line, "right", 0.0);
      manual_remaining_steps_ = static_cast<int>(extract_number(line, "duration_steps", 1.0));
      manual_override_active_ = true;
      send_response_ok(request_id, "{\"left\":" + number_to_string(manual_left_) + ",\"right\":" + number_to_string(manual_right_) +
                                     ",\"remaining_steps\":" + std::to_string(manual_remaining_steps_) + "}");
    } else if (action == "clear_manual_override") {
      manual_override_active_ = false;
      manual_remaining_steps_ = 0;
      send_response_ok(request_id, "{\"cleared\":true}");
    } else if (action == "set_paused") {
      paused_ = extract_bool(line, "paused", true);
      send_response_ok(request_id, std::string("{\"paused\":") + (paused_ ? "true" : "false") + "}");
    } else if (action == "capture_camera") {
      pending_captures_.push_back(PendingCapture{
          request_id,
          extract_string(line, "camera").empty() ? default_camera_ : extract_string(line, "camera"),
          extract_string(line, "path"),
      });
    }
  }

  void handle_pending_captures(const std::vector<CameraFrame> &camera_frames) {
    for (const auto &capture : pending_captures_) {
      auto frame = std::find_if(camera_frames.begin(), camera_frames.end(), [&](const CameraFrame &candidate) {
        return candidate.name == capture.camera;
      });
      if (frame == camera_frames.end()) {
        send_response_error(capture.request_id, "Requested camera frame is not available.");
        continue;
      }
      write_ppm(capture.path, *frame);
      send_response_ok(capture.request_id,
                       "{\"path\":\"" + escape(capture.path) + "\",\"width\":" + std::to_string(frame->width) + ",\"height\":" +
                           std::to_string(frame->height) + "}");
    }
    pending_captures_.clear();
  }

  void write_ppm(const std::string &path, const CameraFrame &frame) {
    std::ofstream output(path, std::ios::binary);
    output << "P6\n" << frame.width << " " << frame.height << "\n255\n";
    for (int y = 0; y < frame.height; ++y) {
      for (int x = 0; x < frame.width; ++x) {
        const int index = 4 * (y * frame.width + x);
        const unsigned char blue = frame.image[index];
        const unsigned char green = frame.image[index + 1];
        const unsigned char red = frame.image[index + 2];
        output.put(static_cast<char>(red));
        output.put(static_cast<char>(green));
        output.put(static_cast<char>(blue));
      }
    }
  }

  void send_line(const std::string &line) {
    if (socket_ == INVALID_SOCKET)
      return;
    const char *data = line.c_str();
    int remaining = static_cast<int>(line.size());
    while (remaining > 0) {
      int sent = send(socket_, data, remaining, 0);
      if (sent <= 0)
        throw std::runtime_error("Runtime socket send failed.");
      data += sent;
      remaining -= sent;
    }
  }

  void send_response_ok(const std::string &request_id, const std::string &result_json) {
    send_line("{\"kind\":\"response\",\"request_id\":\"" + escape(request_id) + "\",\"ok\":true,\"result\":" + result_json + "}\n");
  }

  void send_response_error(const std::string &request_id, const std::string &error_message) {
    send_line("{\"kind\":\"response\",\"request_id\":\"" + escape(request_id) + "\",\"ok\":false,\"error\":\"" +
              escape(error_message) + "\"}\n");
  }

  static std::string map_to_json(const std::map<std::string, double> &values) {
    std::ostringstream payload;
    payload << "{";
    bool first = true;
    for (const auto &[key, value] : values) {
      if (!first)
        payload << ",";
      first = false;
      payload << "\"" << escape(key) << "\":" << number_to_string(value);
    }
    payload << "}";
    return payload.str();
  }

  static std::string number_to_string(double value) {
    std::ostringstream stream;
    stream << value;
    return stream.str();
  }

  static std::string escape(const std::string &value) {
    std::ostringstream escaped;
    for (char ch : value) {
      switch (ch) {
      case '\\':
        escaped << "\\\\";
        break;
      case '"':
        escaped << "\\\"";
        break;
      case '\n':
        escaped << "\\n";
        break;
      case '\r':
        escaped << "\\r";
        break;
      case '\t':
        escaped << "\\t";
        break;
      default:
        escaped << ch;
      }
    }
    return escaped.str();
  }

  static std::string unescape(std::string value) {
    std::string result;
    bool escape_next = false;
    for (char ch : value) {
      if (escape_next) {
        switch (ch) {
        case '\\':
          result.push_back('\\');
          break;
        case '"':
          result.push_back('"');
          break;
        case 'n':
          result.push_back('\n');
          break;
        case 'r':
          result.push_back('\r');
          break;
        case 't':
          result.push_back('\t');
          break;
        default:
          result.push_back(ch);
          break;
        }
        escape_next = false;
      } else if (ch == '\\') {
        escape_next = true;
      } else {
        result.push_back(ch);
      }
    }
    return result;
  }

  static std::string extract_string(const std::string &payload, const std::string &key) {
    std::regex pattern("\"" + key + "\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"");
    std::smatch match;
    if (std::regex_search(payload, match, pattern))
      return unescape(match[1].str());
    return "";
  }

  static double extract_number(const std::string &payload, const std::string &key, double fallback) {
    std::regex pattern("\"" + key + "\"\\s*:\\s*([-0-9.eE]+)");
    std::smatch match;
    if (std::regex_search(payload, match, pattern))
      return std::stod(match[1].str());
    return fallback;
  }

  static bool extract_bool(const std::string &payload, const std::string &key, bool fallback) {
    std::regex pattern("\"" + key + "\"\\s*:\\s*(true|false)");
    std::smatch match;
    if (std::regex_search(payload, match, pattern))
      return match[1].str() == "true";
    return fallback;
  }

  webots::Robot *robot_ = nullptr;
  std::string default_camera_;
  SOCKET socket_ = INVALID_SOCKET;
  bool paused_ = false;
  bool manual_override_active_ = false;
  double manual_left_ = 0.0;
  double manual_right_ = 0.0;
  int manual_remaining_steps_ = 0;
  int step_index_ = 0;
  std::string recv_buffer_;
  std::vector<PendingCapture> pending_captures_;
};

} // namespace webots_mcp_kit

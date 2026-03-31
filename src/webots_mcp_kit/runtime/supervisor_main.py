from __future__ import annotations

import os

from controller import Supervisor

from webots_mcp_kit.runtime_io import connect_runtime


def main() -> None:
    supervisor = Supervisor()
    time_step = int(supervisor.getBasicTimeStep())
    target_def = os.environ.get("WEBOTS_TARGET_DEF", "EPUCK")
    robot_node = supervisor.getFromDef(target_def)
    if robot_node is not None:
        robot_node.saveState("mcp_initial_state")
        robot_node.enableContactPointsTracking(time_step, True)

    client = connect_runtime(
        os.environ["WEBOTS_MCP_HOST"],
        int(os.environ["WEBOTS_MCP_PORT"]),
        role="supervisor",
        name=supervisor.getName(),
        meta={"target_robot": os.environ.get("WEBOTS_TARGET_ROBOT", "epuck-line-follower"), "target_def": target_def},
    )

    step_index = 0
    while supervisor.step(time_step) != -1:
        step_index += 1
        for message in client.drain():
            if message.get("kind") != "command":
                continue
            try:
                if message["action"] == "reset":
                    if robot_node is None:
                        raise RuntimeError("Target robot node is not available for reset.")
                    robot_node.loadState("mcp_initial_state")
                    robot_node.resetPhysics()
                    result = {"reset": True}
                else:
                    raise ValueError(f"Unsupported supervisor command: {message['action']}")
                client.send({"kind": "response", "request_id": message["request_id"], "ok": True, "result": result})
            except Exception as exc:
                client.send({"kind": "response", "request_id": message["request_id"], "ok": False, "error": str(exc)})

        state = {
            "robot_time": round(float(supervisor.getTime()), 6),
            "step_index": step_index,
            "mode": int(supervisor.simulationGetMode()),
            "world_path": supervisor.getWorldPath(),
        }
        if robot_node is not None:
            state["robot_position"] = [round(value, 6) for value in robot_node.getPosition()]
            state["robot_velocity"] = [round(value, 6) for value in robot_node.getVelocity()]
            state["contact_points_count"] = len(robot_node.getContactPoints(True))
        client.send({"kind": "telemetry", "role": "supervisor", "name": supervisor.getName(), "state": state})


if __name__ == "__main__":
    main()

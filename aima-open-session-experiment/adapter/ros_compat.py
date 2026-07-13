"""Tiny ROS2 compatibility layer for GPU images without the ROS2 bridge.

GenieSim's APICore imports ROS message classes even when ``enable_ros`` is
false.  GPUFree's preinstalled image does not ship the ROS2 shared libraries,
so this file provides no-op message/publisher classes strictly for the
non-ROS adapter path.  It is not a ROS protocol implementation and is never
exposed outside the loopback process.
"""

from __future__ import annotations

import sys
import types
from typing import Any


class _Message:
    def __init__(self, **kwargs: Any):
        self.__dict__.update(kwargs)

    def __getattr__(self, name: str) -> Any:
        value = _Message()
        setattr(self, name, value)
        return value


class _Publisher:
    def publish(self, _message: Any) -> None:
        return


class _Clock:
    def now(self) -> "_Clock":
        return self

    def to_msg(self) -> _Message:
        return _Message(sec=0, nanosec=0)


class _Node:
    def __init__(self, *_args: Any, **_kwargs: Any):
        self._clock = _Clock()

    def create_publisher(self, *_args: Any, **_kwargs: Any) -> _Publisher:
        return _Publisher()

    def create_subscription(self, *_args: Any, **_kwargs: Any) -> _Message:
        return _Message()

    def create_timer(self, *_args: Any, **_kwargs: Any) -> _Message:
        return _Message()

    def create_rate(self, *_args: Any, **_kwargs: Any) -> _Message:
        return _Message()

    def get_clock(self) -> _Clock:
        return self._clock

    def get_logger(self) -> _Message:
        return _Message()


class _Parameter:
    class Type:
        BOOL = bool

    def __init__(self, name: str, kind: Any, value: Any):
        self.name, self.kind, self.value = name, kind, value


class _Context:
    def ok(self) -> bool:
        return True


def _module(name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def install_ros_stubs() -> None:
    if "rclpy" in sys.modules:
        return
    context = _Context()
    rclpy = _module(
        "rclpy",
        init=lambda *_args, **_kwargs: None,
        shutdown=lambda: None,
        get_default_context=lambda: context,
        spin_once=lambda *_args, **_kwargs: None,
    )
    rclpy.__path__ = []  # type: ignore[attr-defined]
    _module("rclpy.node", Node=_Node)
    _module("rclpy.parameter", Parameter=_Parameter)
    _module("rclpy.constants", S_TO_NS=1_000_000_000)
    _module(
        "rclpy.qos",
        QoSProfile=lambda **kwargs: _Message(**kwargs),
        QoSHistoryPolicy=_Message(KEEP_LAST=1),
        QoSReliabilityPolicy=_Message(RELIABLE=1),
        QoSDurabilityPolicy=_Message(TRANSIENT_LOCAL=1, VOLATILE=2),
    )
    rclpy.node = sys.modules["rclpy.node"]
    rclpy.parameter = sys.modules["rclpy.parameter"]
    rclpy.qos = sys.modules["rclpy.qos"]

    _module("cv_bridge", CvBridge=type("CvBridge", (), {"imgmsg_to_cv2": lambda *_a, **_k: None}))
    _module("builtin_interfaces.msg", Time=type("Time", (_Message,), {}))
    _module(
        "std_msgs.msg",
        Header=type("Header", (_Message,), {}),
        Bool=type("Bool", (_Message,), {}),
        String=type("String", (_Message,), {}),
    )
    _module(
        "sensor_msgs.msg",
        Image=type("Image", (_Message,), {}),
        CompressedImage=type("CompressedImage", (_Message,), {}),
        JointState=type("JointState", (_Message,), {}),
    )
    _module(
        "geometry_msgs.msg",
        TransformStamped=type("TransformStamped", (_Message,), {}),
        Point=type("Point", (_Message,), {}),
        Vector3=type("Vector3", (_Message,), {}),
        Quaternion=type("Quaternion", (_Message,), {}),
    )
    _module("tf2_msgs.msg", TFMessage=type("TFMessage", (_Message,), {}))
    _module("rosgraph_msgs.msg", Clock=type("Clock", (_Message,), {}))
    broadcaster = type("Broadcaster", (), {"__init__": lambda self, *_a, **_k: None, "sendTransform": lambda self, *_a: None})
    _module("tf2_ros", TransformBroadcaster=broadcaster, StaticTransformBroadcaster=broadcaster)


__all__ = ["install_ros_stubs"]

# -*- coding: utf-8 -*-
"""
Copyright (c) 2008-2025 synodriver <diguohuangjiajinweijun@gmail.com>
"""

import asyncio
import json
import os
import uuid
import gmqtt
import psutil   # type: ignore

discovery_prefix = "homeassistant"
component = "device"
object_id = str(uuid.getnode())

REPORT_INTERVAL = os.getenv("REPORT_INTERVAL") or 5  # seconds
BROKER_IP = os.getenv("BROKER_IP") or "192.168.0.27"
BROKER_PORT = os.getenv("BROKER_PORT") or 1883
BROKER_USER = os.getenv("BROKER_USER") or "synodriver"
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD") or "synodriver"

discovery_topic = "%s/%s/%s/config" % (discovery_prefix, component, object_id)
availability_topic = "%s/%s/%s/availability" % (discovery_prefix, component, object_id)
state_topic = "%s/%s/%s/state" % (discovery_prefix, component, object_id)
command_topic = "%s/%s/%s/set" % (discovery_prefix, component, object_id)

discovery_payload = {
    "device": {
        "identifiers": [object_id],
        "name": "PC",
        "manufacturer": "Synodriver Corp",
        "model": "synosensor 01",
        "sw_version": "0.1",
        "serial_number": object_id,
        "hw_version": "0.1",
    },
    "origin": {
        "name": "PC",
        "sw_version": "0.1",
        "support_url": "https://github.com/synodriver",
    },
    "cmps": {
        "%s.cpu_temperature" % object_id: {
            "platform": "sensor",
            "device_class": "temperature",
            "name": "CPU Temperature",
            "unit_of_measurement": "°C",
            "value_template": "{{ value_json.temperature}}",
            "unique_id": "%s.temperature" % object_id,
            "icon": "mdi:cpu-64-bit",
        },
        "%s.cpu" % object_id: {
            "platform": "sensor",
            "name": "CPU Usage",
            "unit_of_measurement": "%",
            "value_template": "{{ value_json.cpu}}",
            "unique_id": "%s.cpu" % object_id,
            "icon": "mdi:cpu-64-bit",
        },
        "%s.memory" % object_id: {
            "platform": "sensor",
            "name": "Memory Usage",
            "unit_of_measurement": "%",
            "value_template": "{{ value_json.memory}}",
            "unique_id": "%s.memory" % object_id,
            "icon": "mdi:memory",
        },
        "%s.disk" % object_id: {
            "platform": "sensor",
            "name": "Disk Usage",
            "unit_of_measurement": "%",
            "value_template": "{{ value_json.disk}}",
            "unique_id": "%s.disk" % object_id,
            "icon": "mdi:harddisk",
        },
        "%s.rx_bps" % object_id: {
            "platform": "sensor",
            "name": "RX Speed",
            "unit_of_measurement": "B/s",
            "value_template": "{{ value_json.rx_bps }}",
            "unique_id": "%s.rx_bps" % object_id,
            "icon": "mdi:download-network",
        },
        "%s.tx_bps" % object_id: {
            "platform": "sensor",
            "name": "TX Speed",
            "unit_of_measurement": "B/s",
            "value_template": "{{ value_json.tx_bps }}",
            "unique_id": "%s.tx_bps" % object_id,
            "icon": "mdi:upload-network",
        },
    },
    "state_topic": state_topic,
    "availability_topic": availability_topic,
    "qos": 2,
}


def on_connect(client, flags, rc, properties):
    print("Connected")
    client.subscribe(f"{discovery_prefix}/#", qos=2)


def on_message(client, topic, payload, qos, properties):
    print(f"RECV MSG from {topic}:", payload)


def on_disconnect(client, packet, exc=None):
    print("Disconnected")


def on_subscribe(client, mid, qos, properties):
    print("SUBSCRIBED")


async def get_network_speed(interval) -> tuple[float, float]:
    """
    获取网络速度，单位为字节/秒
    Returns:
        tuple[float, float]: 上行速度, 下行速度（字节/秒）
    """
    net1 = psutil.net_io_counters()
    await asyncio.sleep(interval)
    net2 = psutil.net_io_counters()
    up_speed = (net2.bytes_sent - net1.bytes_sent) / interval
    down_speed = (net2.bytes_recv - net1.bytes_recv) / interval
    return up_speed, down_speed


def get_cpu_temperature():
    try:
        temperatures = psutil.sensors_temperatures()
        if "coretemp" in temperatures:
            for entry in temperatures["coretemp"]:
                if entry.label == "Package id 0":
                    return entry.current
    except Exception as e:
        return 40
    return None


async def main():
    will_message = gmqtt.Message(
        availability_topic, b"offline", 2, will_delay_interval=10
    )
    mqttc = gmqtt.Client(client_id=object_id, will_message=will_message)

    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect
    mqttc.on_subscribe = on_subscribe

    mqttc.set_auth_credentials(BROKER_USER, BROKER_PASSWORD)
    await mqttc.connect(BROKER_IP, BROKER_PORT)

    mqttc.publish(discovery_topic, json.dumps(discovery_payload), qos=2)
    mqttc.publish(availability_topic, b"online", qos=2)
    while True:
        cpu = psutil.cpu_percent(interval=1) / psutil.cpu_count()
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        tx_bps, rx_bps = await get_network_speed(REPORT_INTERVAL)
        payload = {
            "cpu": cpu,
            "memory": memory,
            "temperature": get_cpu_temperature(),
            "disk": disk,
            "rx_bps": rx_bps,
            "tx_bps": tx_bps,
        }
        mqttc.publish(state_topic, json.dumps(payload), qos=2)
        # await asyncio.sleep(5) 上面有了网速interval了，不需要再sleep了


if __name__ == "__main__":
    asyncio.run(main())

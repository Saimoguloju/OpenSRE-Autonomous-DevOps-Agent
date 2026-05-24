import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List

from config import config

logger = logging.getLogger(__name__)

SIMULATED_INSTANCES = [
    {"id": "i-0abc123def456789", "type": "t3.medium", "state": "running", "name": "api-server-1"},
    {"id": "i-0def456abc789012", "type": "t3.large", "state": "running", "name": "worker-1"},
]


def get_cloudwatch_metrics(namespace: str, metric_name: str, instance_id: str, minutes: int = 5) -> Dict[str, Any]:
    """Fetch CloudWatch metrics for an EC2 instance."""
    if config.simulation_mode:
        import random
        return {
            "metric": metric_name,
            "instance_id": instance_id,
            "datapoints": [
                {"timestamp": (datetime.now(UTC) - timedelta(minutes=i)).isoformat(), "value": random.uniform(70, 99)}
                for i in range(minutes, 0, -1)
            ],
            "unit": "Percent",
        }

    try:
        import boto3
        cw = boto3.client(
            "cloudwatch",
            region_name=config.aws_region,
            aws_access_key_id=config.aws_access_key_id or None,
            aws_secret_access_key=config.aws_secret_access_key or None,
        )
        end = datetime.now(UTC)
        start = end - timedelta(minutes=minutes)
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start,
            EndTime=end,
            Period=60,
            Statistics=["Average"],
        )
        return {
            "metric": metric_name,
            "instance_id": instance_id,
            "datapoints": [
                {"timestamp": d["Timestamp"].isoformat(), "value": d["Average"]}
                for d in sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])
            ],
            "unit": resp.get("Label", ""),
        }
    except Exception as e:
        logger.error("CloudWatch error: %s", e)
        return {"error": str(e)}


def describe_instances() -> List[Dict[str, Any]]:
    """List EC2 instances."""
    if config.simulation_mode:
        return SIMULATED_INSTANCES

    try:
        import boto3
        ec2 = boto3.client(
            "ec2",
            region_name=config.aws_region,
            aws_access_key_id=config.aws_access_key_id or None,
            aws_secret_access_key=config.aws_secret_access_key or None,
        )
        resp = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["running"]}])
        instances = []
        for reservation in resp["Reservations"]:
            for inst in reservation["Instances"]:
                name = next((t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"), inst["InstanceId"])
                instances.append({
                    "id": inst["InstanceId"],
                    "type": inst["InstanceType"],
                    "state": inst["State"]["Name"],
                    "name": name,
                })
        return instances
    except Exception as e:
        logger.error("describe_instances error: %s", e)
        return []

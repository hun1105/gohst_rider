import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory('tb3_dynamic_detector')
    config = os.path.join(package_share, 'config', 'detector.yaml')

    return LaunchDescription([
        Node(
            package='tb3_dynamic_detector',
            executable='dynamic_detector',
            name='tb3_dynamic_detector',
            output='screen',
            parameters=[config],
        ),
    ])

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    detector_share = get_package_share_directory('tb3_dynamic_detector')
    cartographer_share = get_package_share_directory('turtlebot3_cartographer')
    detector_config = os.path.join(detector_share, 'config', 'detector.yaml')
    cartographer_launch = os.path.join(
        cartographer_share, 'launch', 'cartographer.launch.py'
    )

    return LaunchDescription([
        Node(
            package='tb3_dynamic_detector',
            executable='dynamic_detector',
            name='tb3_dynamic_detector',
            output='screen',
            parameters=[detector_config],
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(cartographer_launch),
        ),
    ])

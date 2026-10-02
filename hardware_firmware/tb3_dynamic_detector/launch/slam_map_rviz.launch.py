import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from tb3_dynamic_detector.paths import map_path


def generate_launch_description():
    package_share = get_package_share_directory('tb3_dynamic_detector')
    cartographer_share = get_package_share_directory('turtlebot3_cartographer')

    cartographer_launch = os.path.join(
        cartographer_share,
        'launch',
        'cartographer.launch.py',
    )
    rviz_config = os.path.join(package_share, 'rviz', 'slam_map.rviz')

    start_rviz = LaunchConfiguration('start_rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')
    map_path = LaunchConfiguration('map_path')
    append_timestamp = LaunchConfiguration('append_timestamp')
    save_on_shutdown = LaunchConfiguration('save_on_shutdown')
    accumulate_map = LaunchConfiguration('accumulate_map')
    filtered_map_threshold = LaunchConfiguration('filtered_map_threshold')

    cartographer = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(cartographer_launch),
        launch_arguments={
            'use_rviz': 'false',
            'use_sim_time': use_sim_time,
        }.items(),
    )

    map_saver = Node(
        package='tb3_dynamic_detector',
        executable='map_snapshot_saver',
        name='tb3_map_snapshot_saver',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'map_path': map_path,
            'append_timestamp': append_timestamp,
            'save_on_shutdown': save_on_shutdown,
            'accumulate_map': accumulate_map,
            'filtered_map_threshold': filtered_map_threshold,
        }],
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(start_rviz),
    )

    return LaunchDescription([
        SetEnvironmentVariable('TURTLEBOT3_MODEL', 'burger'),
        DeclareLaunchArgument('start_rviz', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'map_path',
            default_value=map_path('tb3_map'),
            description='Map output path without extension.',
        ),
        DeclareLaunchArgument('append_timestamp', default_value='true'),
        DeclareLaunchArgument('save_on_shutdown', default_value='true'),
        DeclareLaunchArgument('accumulate_map', default_value='true'),
        DeclareLaunchArgument('filtered_map_threshold', default_value='70'),
        cartographer,
        map_saver,
        rviz,
    ])

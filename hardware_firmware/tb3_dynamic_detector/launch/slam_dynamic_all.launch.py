import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap

from tb3_dynamic_detector.paths import map_path


def generate_launch_description():
    detector_share = get_package_share_directory('tb3_dynamic_detector')
    cartographer_share = get_package_share_directory('turtlebot3_cartographer')

    detector_config = os.path.join(detector_share, 'config', 'detector.yaml')
    cartographer_launch = os.path.join(
        cartographer_share,
        'launch',
        'cartographer.launch.py',
    )
    default_rviz_config = os.path.join(
        os.path.expanduser('~'),
        'tb3_dynamic_ws',
        'dynamic_slam.rviz',
    )

    start_rviz = LaunchConfiguration('start_rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')
    rviz_config = LaunchConfiguration('rviz_config')
    map_path = LaunchConfiguration('map_path')
    append_timestamp = LaunchConfiguration('append_timestamp')
    save_on_shutdown = LaunchConfiguration('save_on_shutdown')
    accumulate_map = LaunchConfiguration('accumulate_map')
    filtered_map_threshold = LaunchConfiguration('filtered_map_threshold')
    detector_delay = LaunchConfiguration('detector_delay')
    latest_tf_fallback = LaunchConfiguration('latest_tf_fallback')

    detector = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_detector',
        name='tb3_dynamic_detector',
        output='screen',
        parameters=[
            detector_config,
            {
                'use_sim_time': use_sim_time,
                'latest_tf_fallback': latest_tf_fallback,
            },
        ],
    )

    delayed_detector = TimerAction(
        period=detector_delay,
        actions=[detector],
    )

    map_filter = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_map_filter',
        name='dynamic_map_filter',
        output='screen',
        parameters=[detector_config, {'use_sim_time': use_sim_time}],
    )

    cartographer = GroupAction([
        SetRemap(src='/scan', dst='/scan_static'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(cartographer_launch),
            launch_arguments={
                'use_rviz': 'false',
                'use_sim_time': use_sim_time,
            }.items(),
        ),
    ])

    map_saver = Node(
        package='tb3_dynamic_detector',
        executable='map_snapshot_saver',
        name='tb3_map_snapshot_saver',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'map_topic': '/map_static',
            'clear_unknown_cells': True,
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
        DeclareLaunchArgument(
            'start_rviz',
            default_value='true',
            description='Start RViz with the saved dynamic SLAM configuration.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock.',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=default_rviz_config,
            description='Absolute path to the RViz configuration.',
        ),
        DeclareLaunchArgument(
            'map_path',
            default_value=map_path('tb3_dynamic_map'),
            description='Map output path without extension.',
        ),
        DeclareLaunchArgument('append_timestamp', default_value='true'),
        DeclareLaunchArgument('save_on_shutdown', default_value='true'),
        DeclareLaunchArgument('accumulate_map', default_value='true'),
        DeclareLaunchArgument('filtered_map_threshold', default_value='70'),
        DeclareLaunchArgument(
            'detector_delay',
            default_value='2.0',
            description=(
                'Delay detector startup so Cartographer can warm its TF buffer '
                'before the first /scan_static message.'
            ),
        ),
        DeclareLaunchArgument(
            'latest_tf_fallback',
            default_value='false',
            description=(
                'Use latest TF when exact scan-time TF is unavailable. '
                'Enable only while the robot is stationary.'
            ),
        ),
        delayed_detector,
        map_filter,
        cartographer,
        map_saver,
        rviz,
    ])

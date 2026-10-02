"""Online SLAM, dynamic-object filtering, Frontier exploration, and Dijkstra.

Data flow:
  /scan -> dynamic detector -> /scan_static -> Cartographer -> /map
  /map + /dynamic_clusters -> separate map filter -> /map_static
  /map_static -> Frontier + Nav2 static layer
  /scan (raw) -> Nav2 obstacle layer -> immediate moving-object avoidance
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, LogInfo, SetEnvironmentVariable, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap

from tb3_dynamic_detector.paths import map_path


def generate_launch_description():
    package_share = get_package_share_directory('tb3_dynamic_detector')
    cartographer_share = get_package_share_directory('turtlebot3_cartographer')
    nav2_share = get_package_share_directory('nav2_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time')
    nav_params = LaunchConfiguration('nav_params')
    start_rviz = LaunchConfiguration('start_rviz')
    rviz_config = LaunchConfiguration('rviz_config')
    explore_delay = LaunchConfiguration('explore_delay')
    explore_log_level = LaunchConfiguration('explore_log_level')

    detector_config = os.path.join(package_share, 'config', 'detector.yaml')
    cartographer_launch = os.path.join(
        cartographer_share, 'launch', 'cartographer.launch.py'
    )
    navigation_launch = os.path.join(
        nav2_share, 'launch', 'navigation_launch.py'
    )

    detector = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_detector',
        name='tb3_dynamic_detector',
        output='screen',
        parameters=[detector_config, {'use_sim_time': use_sim_time}],
    )

    map_filter = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_map_filter',
        name='dynamic_map_filter',
        output='screen',
        parameters=[detector_config, {'use_sim_time': use_sim_time}],
    )

    # Cartographer never receives confirmed moving-object scan points.
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

    # The Nav2 static layer normally uses /map.  Remap only Nav2 to the
    # filtered map, while its obstacle layers keep using raw /scan.
    navigation = GroupAction([
        SetRemap(src='/map', dst='/map_static'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(navigation_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'autostart': 'true',
                'params_file': nav_params,
                'use_composition': 'False',
                'use_respawn': 'False',
                'log_level': 'info',
            }.items(),
        ),
    ])

    frontier_adapter = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_frontier_adapter',
        name='dynamic_frontier_adapter',
        output='screen',
        parameters=[{
            'input_topic': '/map_static',
            'output_topic': '/explore_costmap',
            'occupied_threshold': 55,
            'publish_period': 1.0,
        }],
    )

    explore = Node(
        package='explore_lite',
        executable='explore',
        name='explore_node',
        output='screen',
        arguments=['--ros-args', '--log-level', explore_log_level],
        parameters=[
            os.path.join(package_share, 'config', 'explore_params.yaml'),
            {
                'use_sim_time': use_sim_time,
                'costmap_topic': '/explore_costmap',
                'costmap_updates_topic': '/explore_costmap_updates',
            },
        ],
    )

    map_saver = Node(
        package='tb3_dynamic_detector',
        executable='map_snapshot_saver',
        name='tb3_map_snapshot_saver',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'map_topic': '/map_static',
            'map_path': LaunchConfiguration('map_path'),
            'append_timestamp': True,
            'save_on_shutdown': True,
            'accumulate_map': True,
            'filtered_map_threshold': 70,
        }],
    )

    nav2_diagnostics = Node(
        package='tb3_dynamic_detector',
        executable='nav2_failure_diagnostics',
        name='nav2_failure_diagnostics',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'report_period_sec': 10.0,
            'stale_timeout_sec': 2.0,
            'map_timeout_sec': 8.0,
        }],
    )

    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz', output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(start_rviz),
    )

    return LaunchDescription([
        SetEnvironmentVariable('TURTLEBOT3_MODEL', 'burger'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'nav_params',
            default_value=os.path.join(package_share, 'config', 'burger_clearance.yaml'),
        ),
        DeclareLaunchArgument('start_rviz', default_value='true'),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=os.path.join(package_share, 'rviz', 'dynamic_frontier.rviz'),
        ),
        DeclareLaunchArgument('explore_delay', default_value='20.0'),
        DeclareLaunchArgument(
            'explore_log_level',
            default_value='info',
            description='Use explore_node:=debug to print frontier goal decisions.',
        ),
        DeclareLaunchArgument(
            'map_path',
            default_value=map_path('tb3_dynamic_frontier_map'),
        ),
        detector,
        map_filter,
        cartographer,
        navigation,
        frontier_adapter,
        TimerAction(
            period=explore_delay,
            actions=[
                LogInfo(msg='Starting dynamic-map Frontier exploration.'),
                explore,
            ],
        ),
        map_saver,
        nav2_diagnostics,
        rviz,
    ])

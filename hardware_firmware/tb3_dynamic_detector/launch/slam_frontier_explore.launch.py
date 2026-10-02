"""Run online Frontier+Dijkstra exploration with LiDAR dynamic detection.

Pipeline:
  Cartographer -> /map -> trinary map adapter -> Explore Lite frontier goal
  Explore Lite -> NavigateToPose -> Nav2 NavFn (Dijkstra) -> DWB -> /cmd_vel
  /scan -> dynamic_detector -> /dynamic_boxes, /dynamic_clusters

The detector visualizes moving LiDAR clusters. It does not yet remove cells
from Cartographer's map; Nav2 continues to use the live /scan costmap for
collision avoidance.
"""

import os
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from tb3_dynamic_detector.paths import map_path


def _validate_dijkstra_params(context):
    """Fail early if a supplied Nav2 file does not select NavFn Dijkstra."""
    params_path = os.path.abspath(
        os.path.expanduser(LaunchConfiguration('nav_params').perform(context))
    )
    if not os.path.isfile(params_path):
        raise RuntimeError(f'Nav2 parameter file not found: {params_path}')

    with open(params_path, encoding='utf-8') as params_file:
        contents = params_file.read()

    required_patterns = {
        'NavFn planner': r'plugin:\s*["\']?nav2_navfn_planner[/:]NavfnPlanner',
        'Dijkstra mode': r'(?m)^\s*use_astar:\s*[Ff]alse\s*$',
        'unknown-space planning': r'(?m)^\s*allow_unknown:\s*[Tt]rue\s*$',
    }
    missing = [
        label for label, pattern in required_patterns.items()
        if re.search(pattern, contents) is None
    ]
    if missing:
        raise RuntimeError(
            f'Nav2 configuration is not ready for Frontier+Dijkstra: '
            f'{", ".join(missing)}. File: {params_path}'
        )

    return [LogInfo(msg=f'Validated Dijkstra Nav2 parameters: {params_path}')]


def generate_launch_description():
    package_share = get_package_share_directory('tb3_dynamic_detector')
    cartographer_share = get_package_share_directory('turtlebot3_cartographer')
    navigation_share = get_package_share_directory('turtlebot3_navigation2')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    cartographer_launch = os.path.join(
        cartographer_share,
        'launch',
        'cartographer.launch.py',
    )
    navigation_launch = os.path.join(
        nav2_bringup_share,
        'launch',
        'navigation_launch.py',
    )
    official_nav_params = os.path.join(
        navigation_share,
        'param',
        'humble',
        'burger.yaml',
    )
    custom_nav_params = os.path.join(
        package_share,
        'config',
        'burger_clearance.yaml',
    )
    # Use the project's clearance-tuned Nav2 file when it was installed.
    # Fall back to the official Burger values until that file is created.
    default_nav_params = (
        custom_nav_params if os.path.isfile(custom_nav_params)
        else official_nav_params
    )
    explore_params = os.path.join(
        package_share,
        'config',
        'explore_params.yaml',
    )
    detector_config = os.path.join(
        package_share,
        'config',
        'detector.yaml',
    )
    default_rviz_config = os.path.join(
        os.path.expanduser('~'),
        'tb3_dynamic_ws',
        'dynamic_slam.rviz',
    )

    use_sim_time = LaunchConfiguration('use_sim_time')
    nav_params = LaunchConfiguration('nav_params')
    start_explore = LaunchConfiguration('start_explore')
    start_dynamic_detector = LaunchConfiguration('start_dynamic_detector')
    explore_delay = LaunchConfiguration('explore_delay')
    explore_log_level = LaunchConfiguration('explore_log_level')
    explore_costmap_topic = LaunchConfiguration('explore_costmap_topic')
    explore_costmap_updates_topic = LaunchConfiguration('explore_costmap_updates_topic')
    explore_occupied_threshold = LaunchConfiguration('explore_occupied_threshold')
    start_rviz = LaunchConfiguration('start_rviz')
    rviz_config = LaunchConfiguration('rviz_config')
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

    dynamic_detector = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_detector',
        name='tb3_dynamic_detector',
        output='screen',
        parameters=[
            detector_config,
            {
                'use_sim_time': use_sim_time,
                # A moving robot needs the static-support gate and
                # timestamp-accurate transforms to avoid wall false positives.
                'require_low_static_support': True,
                'latest_tf_fallback': False,
                'enable_displacement_detection': False,
                'foreground_only_detection': False,
            },
        ],
        condition=IfCondition(start_dynamic_detector),
    )

    # navigation_launch.py intentionally excludes AMCL and map_server.
    # Cartographer owns /map and the map -> odom transform during online SLAM.
    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(navigation_launch),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': 'true',
            'params_file': nav_params,
            # Humble evaluates use_composition with PythonExpression.
            # It therefore requires Python-style True/False capitalization.
            'use_composition': 'False',
            'use_respawn': 'False',
            'log_level': 'info',
        }.items(),
    )

    explore = Node(
        package='explore_lite',
        executable='explore',
        name='explore_node',
        output='screen',
        arguments=['--ros-args', '--log-level', explore_log_level],
        parameters=[
            explore_params,
            {
                'use_sim_time': use_sim_time,
                'costmap_topic': explore_costmap_topic,
                'costmap_updates_topic': explore_costmap_updates_topic,
            },
        ],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
        condition=IfCondition(start_explore),
    )

    delayed_explore = TimerAction(
        period=explore_delay,
        actions=[
            LogInfo(msg='Starting Explore Lite frontier exploration.'),
            explore,
        ],
        condition=IfCondition(start_explore),
    )

    # Explore Lite requires exact free(0) cells. Cartographer instead often
    # emits known-free probability cells in the 1..49 range.
    explore_map_adapter = Node(
        package='tb3_dynamic_detector',
        executable='explore_map_adapter',
        name='explore_map_adapter',
        output='screen',
        parameters=[{
            'input_topic': '/map',
            'output_topic': explore_costmap_topic,
            'occupied_threshold': explore_occupied_threshold,
            'publish_period': 1.0,
        }],
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
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'nav_params',
            default_value=default_nav_params,
            description=(
                'Nav2 parameters. Burger default uses NavFn with '
                'use_astar=false (Dijkstra) and allow_unknown=true.'
            ),
        ),
        DeclareLaunchArgument('start_explore', default_value='true'),
        DeclareLaunchArgument(
            'start_dynamic_detector',
            default_value='true',
            description='Start LiDAR moving-object boxes and velocity arrows.',
        ),
        DeclareLaunchArgument(
            'explore_delay',
            default_value='20.0',
            description='Seconds to wait for Cartographer and Nav2 startup.',
        ),
        DeclareLaunchArgument(
            'explore_log_level',
            default_value='info',
            description='Explore Lite logging level. Use debug to inspect frontier selection.',
        ),
        DeclareLaunchArgument(
            'explore_costmap_topic',
            default_value='/explore_costmap',
            description='Trinary OccupancyGrid used by Explore Lite for frontier search.',
        ),
        DeclareLaunchArgument(
            'explore_costmap_updates_topic',
            default_value='/explore_costmap_updates',
            description='Incremental update topic paired with explore_costmap_topic.',
        ),
        DeclareLaunchArgument(
            'explore_occupied_threshold',
            # Relax 50 -> 55 so uncertain 50..54 map cells are treated as
            # free for frontier detection. Nav2 still performs final safety
            # checking with its own live costmaps.
            default_value='55',
            description=(
                'Cartographer occupancy value treated as an obstacle. '
                'Values below it are converted to free space.'
            ),
        ),
        DeclareLaunchArgument('start_rviz', default_value='true'),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=default_rviz_config,
        ),
        DeclareLaunchArgument(
            'map_path',
            default_value=map_path('tb3_frontier_map'),
            description='Map output path without extension.',
        ),
        DeclareLaunchArgument('append_timestamp', default_value='true'),
        DeclareLaunchArgument('save_on_shutdown', default_value='true'),
        DeclareLaunchArgument('accumulate_map', default_value='true'),
        DeclareLaunchArgument('filtered_map_threshold', default_value='70'),
        LogInfo(msg='Online SLAM mode: AMCL and saved-map server are disabled.'),
        LogInfo(msg='Global planner: NavFn Dijkstra (use_astar=false).'),
        LogInfo(msg='Dynamic detector: /scan -> /dynamic_boxes (visualization only).'),
        OpaqueFunction(function=_validate_dijkstra_params),
        cartographer,
        dynamic_detector,
        navigation,
        explore_map_adapter,
        map_saver,
        rviz,
        delayed_explore,
    ])

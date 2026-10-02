"""Online SLAM, dynamic-object filtering, Frontier exploration, and Dijkstra.

Data flow:
  /scan + /imu + /odom -> freshness filter -> /*_fresh
  /scan_fresh -> dynamic detector -> /scan_static -> Cartographer -> /map
  /map + /dynamic_clusters -> separate map filter -> /map_static
  /map_static -> Frontier + Nav2 static layer
  /scan_fresh -> Nav2 obstacle layer -> immediate moving-object avoidance
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, LogInfo, SetEnvironmentVariable, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue

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
    scan_max_age = LaunchConfiguration('scan_max_age')
    imu_max_age = LaunchConfiguration('imu_max_age')
    odom_max_age = LaunchConfiguration('odom_max_age')
    future_tolerance = LaunchConfiguration('future_tolerance')

    detector_config = os.path.join(package_share, 'config', 'detector.yaml')
    cartographer_launch = os.path.join(
        cartographer_share, 'launch', 'cartographer.launch.py'
    )
    navigation_launch = os.path.join(
        nav2_share, 'launch', 'navigation_launch.py'
    )

    freshness_filter = Node(
        package='tb3_dynamic_detector',
        executable='sensor_freshness_filter',
        name='sensor_freshness_filter',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'scan_input_topic': '/scan',
            'scan_output_topic': '/scan_fresh',
            'imu_input_topic': '/imu',
            'imu_output_topic': '/imu_fresh',
            'odom_input_topic': '/odom',
            'odom_output_topic': '/odom_fresh',
            'scan_max_age_sec': ParameterValue(scan_max_age, value_type=float),
            'imu_max_age_sec': ParameterValue(imu_max_age, value_type=float),
            'odom_max_age_sec': ParameterValue(odom_max_age, value_type=float),
            'future_tolerance_sec': ParameterValue(
                future_tolerance, value_type=float
            ),
            'reset_backwards_sec': 1.0,
            'status_period_sec': 5.0,
            'warning_throttle_sec': 2.0,
        }],
    )

    detector = Node(
        package='tb3_dynamic_detector',
        executable='dynamic_detector',
        name='tb3_dynamic_detector',
        output='screen',
        parameters=[detector_config, {'use_sim_time': use_sim_time}],
        remappings=[
            ('/scan', '/scan_fresh'),
            ('/odom', '/odom_fresh'),
        ],
    )

    # Keep OccupancyGrid masking outside the 10 Hz scan-tracking process.
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
        SetRemap(src='/imu', dst='/imu_fresh'),
        SetRemap(src='/odom', dst='/odom_fresh'),
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
        SetRemap(src='/scan', dst='/scan_fresh'),
        SetRemap(src='/odom', dst='/odom_fresh'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(navigation_launch),
            launch_arguments={
                'use_sim_time': use_sim_time,
                # Keep Nav2's bundled manager passive.  A dedicated Super
                # Client manager below performs lifecycle service calls.
                'autostart': 'false',
                'params_file': nav_params,
                'use_composition': 'False',
                'use_respawn': 'False',
                'log_level': 'info',
            }.items(),
        ),
    ])

    # Fast DDS Discovery Server can keep topic matches while failing to match
    # newly-created lifecycle service endpoints.  Limit Super Client mode to
    # this single manager instead of applying it to every launch child.
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation_super',
        output='screen',
        additional_env={
            'ROS_SUPER_CLIENT': 'TRUE',
        },
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'bond_timeout': 8.0,
            'node_names': [
                'controller_server',
                'smoother_server',
                'planner_server',
                'behavior_server',
                'bt_navigator',
                'waypoint_follower',
                'velocity_smoother',
            ],
        }],
    )

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

    lifecycle_recovery = Node(
        package='tb3_dynamic_detector',
        executable='nav2_lifecycle_recovery',
        name='nav2_lifecycle_recovery',
        output='screen',
        additional_env={'ROS_SUPER_CLIENT': 'TRUE'},
        parameters=[{
            'use_sim_time': use_sim_time,
            'manager_name': '/lifecycle_manager_navigation_super',
            'retry_period_sec': 10.0,
            'startup_grace_sec': 0.0,
            'scan_topic': '/scan_fresh',
            'odom_topic': '/odom_fresh',
            'map_topic': '/map_static',
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
        # Cartographer logs through glog, not rclcpp log levels, so this is
        # the only way to quiet its "[cartographer logger]" INFO/WARN spam
        # (submap/constraint chatter, "Dropped N earlier points") without
        # also losing Nav2/BT/our-own-node log lines.
        SetEnvironmentVariable('GLOG_minloglevel', '2'),
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
            'scan_max_age',
            default_value='0.70',
            description='Drop LaserScan messages older than this many seconds.',
        ),
        DeclareLaunchArgument(
            'imu_max_age',
            default_value='0.50',
            description='Drop IMU messages older than this many seconds.',
        ),
        DeclareLaunchArgument(
            'odom_max_age',
            default_value='0.50',
            description='Drop odometry messages older than this many seconds.',
        ),
        DeclareLaunchArgument(
            'future_tolerance',
            default_value='0.10',
            description='Maximum permitted future timestamp in seconds.',
        ),
        DeclareLaunchArgument(
            'explore_log_level',
            default_value='info',
            description='Use explore_node:=debug to print frontier goal decisions.',
        ),
        DeclareLaunchArgument(
            'map_path',
            default_value=map_path('tb3_dynamic_frontier_map'),
        ),
        freshness_filter,
        detector,
        map_filter,
        cartographer,
        navigation,
        TimerAction(
            period=12.0,
            actions=[
                LogInfo(msg='Starting dedicated Super Client Nav2 lifecycle manager.'),
                lifecycle_manager,
            ],
        ),
        TimerAction(
            period=18.0,
            actions=[
                LogInfo(msg='Starting Nav2 lifecycle recovery watchdog.'),
                lifecycle_recovery,
            ],
        ),
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

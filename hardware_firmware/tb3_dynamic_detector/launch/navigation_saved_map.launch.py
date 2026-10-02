"""Launch TurtleBot3 Navigation2 with the newest saved map by default."""

from glob import glob
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from tb3_dynamic_detector.paths import map_directory


MAP_DIRECTORY = map_directory()


def _newest_saved_map() -> str:
    candidates = glob(os.path.join(MAP_DIRECTORY, '*.yaml'))
    if not candidates:
        return os.path.join(MAP_DIRECTORY, 'map.yaml')
    return max(candidates, key=os.path.getmtime)


def _validate_map(context):
    map_path = os.path.abspath(
        os.path.expanduser(LaunchConfiguration('map').perform(context))
    )
    if not os.path.isfile(map_path):
        raise RuntimeError(
            f'Map YAML not found: {map_path}. '
            'Save a SLAM map first or launch with map:=/absolute/map.yaml'
        )
    return [LogInfo(msg=f'Navigation map: {map_path}')]


def generate_launch_description():
    navigation_share = get_package_share_directory('turtlebot3_navigation2')
    navigation_launch = os.path.join(
        navigation_share,
        'launch',
        'navigation2.launch.py',
    )
    default_params = os.path.join(
        navigation_share,
        'param',
        'humble',
        'burger.yaml',
    )

    map_file = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(navigation_launch),
        launch_arguments={
            'map': map_file,
            'params_file': params_file,
            'use_sim_time': use_sim_time,
        }.items(),
    )

    return LaunchDescription([
        SetEnvironmentVariable('TURTLEBOT3_MODEL', 'burger'),
        DeclareLaunchArgument(
            'map',
            default_value=_newest_saved_map(),
            description='Saved map YAML. Default: newest YAML in outputs/maps.',
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params,
            description='Navigation2 parameter file.',
        ),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        OpaqueFunction(function=_validate_map),
        navigation,
    ])

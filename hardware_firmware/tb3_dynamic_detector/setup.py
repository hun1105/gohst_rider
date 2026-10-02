from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'tb3_dynamic_detector'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hun',
    maintainer_email='hun@localhost',
    description='LiDAR-only dynamic cluster tracking and RViz bounding boxes.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dynamic_detector = tb3_dynamic_detector.dynamic_detector:main',
            'dynamic_map_filter = tb3_dynamic_detector.dynamic_map_filter:main',
            'map_snapshot_saver = tb3_dynamic_detector.map_snapshot_saver:main',
            'map_frontier_probe = tb3_dynamic_detector.map_frontier_probe:main',
            'explore_map_adapter = tb3_dynamic_detector.explore_map_adapter:main',
            'dynamic_frontier_adapter = tb3_dynamic_detector.dynamic_frontier_adapter:main',
            'nav2_failure_diagnostics = tb3_dynamic_detector.nav2_failure_diagnostics:main',
            'nav2_lifecycle_recovery = tb3_dynamic_detector.nav2_lifecycle_recovery:main',
            'sensor_freshness_filter = tb3_dynamic_detector.sensor_freshness_filter:main',
        ],
    },
)

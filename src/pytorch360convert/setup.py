import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'pytorch360convert'

setup(
    name=package_name,
    version='0.2.3',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rover',
    maintainer_email='begeorf@umich.edu',
    description='PyTorch implementation of 360-degree image conversion functions for ROS 2',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ps4_trigger_node = pytorch360convert.ps4_trigger_node:main',
            'theta_driver_node = pytorch360convert.theta_driver_node:main',
            'cubemap_converter_node = pytorch360convert.cubemap_converter_node:main',
            # Legacy node retained for compatibility if needed
            'theta_still_node = pytorch360convert.theta_still_node:main',
        ],
    },
)
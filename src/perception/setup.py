import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'perception'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # FIX: Clean up this line so it only grabs actual launch files
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*.py'))),
        (os.path.join('share', package_name, 'config'), glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@todo.com',
    description='YOLO 3D Object Perception Package',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'yolo_depth_node = perception.yolo_depth_node:main',
            'depth_annotator_node = perception.depth_annotator_node:main',
            'yolo_pointcloud_node = perception.yolo_pointcloud_node:main', # <-- Add this line
            'object_mapper_node = perception.object_mapper_node:main',
            'snapshot_manager_node = perception.snapshot_manager_node:main'
        ],
    },
)
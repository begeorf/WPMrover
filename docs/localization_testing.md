- first test:
```over@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-16_34_20/
[INFO] [1783371197.224961845] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-16_34_20/rosbag2_2026_07_06-16_34_20_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-16_34_20/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1860.30°
Final Integrated /imu_raw:           1860.31°
Final Raw Wheel Odometry:            2790.89°
Final Unwrapped EKF Filter Odom:     3174.41°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: +60.30°  |  Pct Error: 3.35%
Integrated /imu_raw:      Error: +60.31°  |  Pct Error: 3.35%
Raw Wheel Odometry:       Error: +990.89°  |  Pct Error: 55.05%
Fused EKF State:          Error: +1374.41°  |  Pct Error: 76.36%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Second test
- changed the wheel base parameter to be back to the original value it was from roverrobotics
```
over@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-16_34_20/
[INFO] [1783371197.224961845] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-16_34_20/rosbag2_2026_07_06-16_34_20_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-16_34_20/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1860.30°
Final Integrated /imu_raw:           1860.31°
Final Raw Wheel Odometry:            2790.89°
Final Unwrapped EKF Filter Odom:     3174.41°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: +60.30°  |  Pct Error: 3.35%
Integrated /imu_raw:      Error: +60.31°  |  Pct Error: 3.35%
Raw Wheel Odometry:       Error: +990.89°  |  Pct Error: 55.05%
Fused EKF State:          Error: +1374.41°  |  Pct Error: 76.36%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Changed the wheel base parameter again to a value that based on the last 2 test should eliminate all wheel based odom inaccuracies (didn't work)
- Third test
```
over@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-17_09_36/
[INFO] [1783372263.134694135] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-17_09_36/rosbag2_2026_07_06-17_09_36_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-17_09_36/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1860.44°
Final Integrated /imu_raw:           1860.44°
Final Raw Wheel Odometry:            2360.75°
Final Unwrapped EKF Filter Odom:     2705.06°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: +60.44°  |  Pct Error: 3.36%
Integrated /imu_raw:      Error: +60.44°  |  Pct Error: 3.36%
Raw Wheel Odometry:       Error: +560.75°  |  Pct Error: 31.15%
Fused EKF State:          Error: +905.06°  |  Pct Error: 50.28%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Fourth test
```
over@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-17_22_02/
[INFO] [1783373091.891512820] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-17_22_02/rosbag2_2026_07_06-17_22_02_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-17_22_02/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1859.48°
Final Integrated /imu_raw:           1859.48°
Final Raw Wheel Odometry:            2140.80°
Final Unwrapped EKF Filter Odom:     2466.16°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: +59.48°  |  Pct Error: 3.30%
Integrated /imu_raw:      Error: +59.48°  |  Pct Error: 3.30%
Raw Wheel Odometry:       Error: +340.80°  |  Pct Error: 18.93%
Fused EKF State:          Error: +666.16°  |  Pct Error: 37.01%
====================================================================
```

- Fifth test
```
rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-17_30_30/
[INFO] [1783373519.172170776] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-17_30_30/rosbag2_2026_07_06-17_30_30_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-17_30_30/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1853.02°
Final Integrated /imu_raw:           1853.03°
Final Raw Wheel Odometry:            2229.37°
Final Unwrapped EKF Filter Odom:     2507.96°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: +53.02°  |  Pct Error: 2.95%
Integrated /imu_raw:      Error: +53.03°  |  Pct Error: 2.95%
Raw Wheel Odometry:       Error: +429.37°  |  Pct Error: 23.85%
Fused EKF State:          Error: +707.96°  |  Pct Error: 39.33%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
rover@rover-desktop:~/rover_workspace$ 
```

- Test 6: only 360 degrees; this is to test if the IMU error is constant or only when it's accelerating. Same percentage error as the previous tests means it's constant, same degree difference means its based on accelerations.
```
rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-18_13_35/
[INFO] [1783376057.431852689] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-18_13_35/rosbag2_2026_07_06-18_13_35_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-18_13_35/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          372.72°
Final Integrated /imu_raw:           372.72°
Final Raw Wheel Odometry:            273.08°
Final Unwrapped EKF Filter Odom:     365.87°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 360

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 360.0°)
====================================================================
Integrated /imu/data:     Error: +12.72°  |  Pct Error: 3.53%
Integrated /imu_raw:      Error: +12.72°  |  Pct Error: 3.53%
Raw Wheel Odometry:       Error: -86.92°  |  Pct Error: 24.15%
Fused EKF State:          Error: +5.87°  |  Pct Error: 1.63%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Test 7: same conditions as test 6, trying to get average error
```rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-18_16_55/
[INFO] [1783376250.978960821] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-18_16_55/rosbag2_2026_07_06-18_16_55_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-18_16_55/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          372.28°
Final Integrated /imu_raw:           372.28°
Final Raw Wheel Odometry:            331.39°
Final Unwrapped EKF Filter Odom:     486.43°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 360

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 360.0°)
====================================================================
Integrated /imu/data:     Error: +12.28°  |  Pct Error: 3.41%
Integrated /imu_raw:      Error: +12.28°  |  Pct Error: 3.41%
Raw Wheel Odometry:       Error: -28.61°  |  Pct Error: 7.95%
Fused EKF State:          Error: +126.43°  |  Pct Error: 35.12%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Test 8: same as test 7
```
rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-18_18_38/
[INFO] [1783376341.222656184] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-18_18_38/rosbag2_2026_07_06-18_18_38_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-18_18_38/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          371.25°
Final Integrated /imu_raw:           371.25°
Final Raw Wheel Odometry:            385.45°
Final Unwrapped EKF Filter Odom:     590.56°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 360

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 360.0°)
====================================================================
Integrated /imu/data:     Error: +11.25°  |  Pct Error: 3.13%
Integrated /imu_raw:      Error: +11.25°  |  Pct Error: 3.13%
Raw Wheel Odometry:       Error: +25.45°  |  Pct Error: 7.07%
Fused EKF State:          Error: +230.56°  |  Pct Error: 64.04%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Test 9
- Added correction factor to bno055 driver
```
rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_06-19_03_46/
[INFO] [1783379061.796206455] [rosbag2_storage]: Opened database 'rosbag2_2026_07_06-19_03_46/rosbag2_2026_07_06-19_03_46_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_06-19_03_46/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1803.26°
Final Integrated /imu_raw:           1803.27°
Final Raw Wheel Odometry:            2125.27°
Final Unwrapped EKF Filter Odom:     2369.10°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: +3.26°  |  Pct Error: 0.18%
Integrated /imu_raw:      Error: +3.27°  |  Pct Error: 0.18%
Raw Wheel Odometry:       Error: +325.27°  |  Pct Error: 18.07%
Fused EKF State:          Error: +569.10°  |  Pct Error: 31.62%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```

- Test 10
```over@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_07-08_58_57/
[INFO] [1783429186.713363717] [rosbag2_storage]: Opened database 'rosbag2_2026_07_07-08_58_57/rosbag2_2026_07_07-08_58_57_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_07-08_58_57/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          718.14°
Final Integrated /imu_raw:           718.15°
Final Raw Wheel Odometry:            833.05°
Final Unwrapped EKF Filter Odom:     931.28°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 720

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 720.0°)
====================================================================
Integrated /imu/data:     Error: -1.86°  |  Pct Error: 0.26%
Integrated /imu_raw:      Error: -1.85°  |  Pct Error: 0.26%
Raw Wheel Odometry:       Error: +113.05°  |  Pct Error: 15.70%
Fused EKF State:          Error: +211.28°  |  Pct Error: 29.34%
====================================================================
```

- Test 11
- The math is messed up here beacause the final position is also zero, but the error is still very low
```
rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_07-09_02_11/
[INFO] [1783429364.802204420] [rosbag2_storage]: Opened database 'rosbag2_2026_07_07-09_02_11/rosbag2_2026_07_07-09_02_11_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_07-09_02_11/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          -0.89°
Final Integrated /imu_raw:           -0.87°
Final Raw Wheel Odometry:            106.01°
Final Unwrapped EKF Filter Odom:     -150.57°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 0

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 0.0°)
====================================================================
Integrated /imu/data:     Error: -0.89°  |  Pct Error: 88.54%
Integrated /imu_raw:      Error: -0.87°  |  Pct Error: 87.24%
Raw Wheel Odometry:       Error: +106.01°  |  Pct Error: 10601.08%
Fused EKF State:          Error: -150.57°  |  Pct Error: 15056.74%
====================================================================
```

- Test 12
- Wrong topic name into EKF filter (that's why no data)
```rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_07-09_18_09/
[INFO] [1783430335.400717827] [rosbag2_storage]: Opened database 'rosbag2_2026_07_07-09_18_09/rosbag2_2026_07_07-09_18_09_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_07-09_18_09/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          1798.97°
Final Integrated /imu_raw:           1798.98°
Final Raw Wheel Odometry:            1974.94°
Final Unwrapped EKF Filter Odom:     0.00°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): 1800

====================================================================
            GROUND TRUTH ERROR REPORT (Target: 1800.0°)
====================================================================
Integrated /imu/data:     Error: -1.03°  |  Pct Error: 0.06%
Integrated /imu_raw:      Error: -1.02°  |  Pct Error: 0.06%
Raw Wheel Odometry:       Error: +174.94°  |  Pct Error: 9.72%
Fused EKF State:          Error: -1800.00°  |  Pct Error: 100.00%
====================================================================
```

- Test 13
- Same as test 12
```rover@rover-desktop:~/rover_workspace$ python3 analyze_spins.py rosbag2_2026_07_07-09_20_45/
[INFO] [1783430469.095278224] [rosbag2_storage]: Opened database 'rosbag2_2026_07_07-09_20_45/rosbag2_2026_07_07-09_20_45_0.db3' for READ_ONLY.
Reading data packets from sqlite3 rosbag: rosbag2_2026_07_07-09_20_45/

--- SPIN LOG PROCESSING COMPLETE ---
Final Integrated /imu/data:          -720.61°
Final Integrated /imu_raw:           -720.62°
Final Raw Wheel Odometry:            -683.24°
Final Unwrapped EKF Filter Odom:     0.00°
------------------------------------

[Input Required]
Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): -720

====================================================================
            GROUND TRUTH ERROR REPORT (Target: -720.0°)
====================================================================
Integrated /imu/data:     Error: -0.61°  |  Pct Error: 0.09%
Integrated /imu_raw:      Error: -0.62°  |  Pct Error: 0.09%
Raw Wheel Odometry:       Error: +36.76°  |  Pct Error: 5.11%
Fused EKF State:          Error: +720.00°  |  Pct Error: 100.00%
====================================================================

Detailed timeline trace exported to: spin_test_results.csv
```
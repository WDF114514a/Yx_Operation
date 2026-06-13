设备IP说明：
1.设备IP分两类：一是型号为T3P-XXXX或T3-XXXX（三位数或四位数，规则一致），IP是10.200.A.BBB，A是XXXX除以200取整，BBB是XXXX除以200取整之后的余数；二是型号为T1-XXX，IP是10.200.10C.DDD，C是XXX除以200取整，DDD是XXX除以200取整之后的余数；此外，国外设备的IP有些许不同，俄罗斯的IP前5位是10.203，其他国外地区的IP前5位是10.202
2.设备ssh连接登录使用设备IP，用户名为root，密码是YunXiang@2021


机器人日志的存储路径在/opt/agv/log下，该目录下存在多个子文件夹对各类型日志进行分类。

绕障日志存放在MotionPlugin文件夹内，常用日志的关键字如下：
LogAvoid_
TrackEntance_
PathPlanner_
grace_interface_
样例：LogAvoid_20260612_143343.log（表示2026年6月12日14点33分43秒的LogAvoid日志）

调度日志存放在TaskSever文件夹内，常用日志关键字如下：
robot_task_
water_level
battery_state
charge_
water_
样例：battery_state_20260607_172010.log（表示2026年6月7日17点20分10秒的battery_state日志）

电气日志存放在agv_shell文件夹内，常用日志关键字如下：
mcmesg_
agv_shell_
样例：agv_shell_20260608_172945.log（表示2026年6月8日17点29分45秒的agv_shell日志）

定位日志存放在StarLoc3D文件夹内，常用日志关键字如下：
LocInfoLog_
LocManager_
LocOutput_
SynSensorData_
样例：LocInfoLog_20260607_182654.log（表示2026年6月6日18点26分54秒的LocInfoLog日志）
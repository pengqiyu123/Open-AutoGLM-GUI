# ADB 命令大全

## 一、基础命令
```bash
adb reboot    # 重启
adb help      # 查看ADB帮助
```

## 二、查看设备
```bash
adb devices   # 查看可连接操作的设备
```

## 三、连接设备
```bash
adb [-d|-e|-s <serialNumber>] <command>
```
参数：
- `-d` 指定当前唯一通过USB连接的Android设备为命令目标
- `-e` 指定当前唯一运行的模拟器为命令目标
- `-s <serialNumber>` 指定相应serialNumber号的设备/模拟器为命令目标

示例：
```bash
adb connect 127.0.0.1:7555      # 以WLAN网络方式连接（如连接模拟器MUMU等）
adb disconnect 127.0.0.1:16416  # 断开连接
adb -s cf27456f shell           # 指定连接设备使用命令
```

## 四、安装、卸载APP应用

### 1. 安装应用
```bash
adb install test.apk           # 安装应用
adb install -r demo.apk        # 保留数据和缓存文件，重新安装apk
adb install -s test.apk        # 安装apk到sd卡
```

### 2. 卸载应用
```bash
adb uninstall cn.com.test.mobile      # 卸载应用，需要指定包
adb uninstall -k cn.com.test.mobile   # 卸载app但保留数据和缓存文件
```

## 五、adb shell

### 5-1. adb shell am

#### 5-1-1. 启动Activity
```bash
adb shell am start -n com.tencent.mm/.ui.LauncherUI           # 调起微信主界面
adb shell am start -n com.android.browser/com.android.browser.BrowserActivity  # 打开浏览器
adb shell am start -a android.intent.action.VIEW -d http://www.163.com/        # 浏览器打开指定网址
```

#### 5-1-4. 强制停止应用
```bash
adb shell am force-stop cn.com.test.mobile  # 强制停止应用
adb shell am force-stop com.tencent.mm      # 强制停止微信
```

### 5-2. adb shell pm

```bash
adb shell pm list packages        # 列出手机装的所有app的包名
adb shell pm list packages -s     # 列出系统应用的所有包名
adb shell pm list packages -3     # 列出除了系统应用的第三方应用包名
adb shell pm clear cn.com.test.mobile  # 清除应用数据与缓存
```

### 5-3. adb shell dumpsys

```bash
adb shell dumpsys package                              # 包信息
adb shell dumpsys meminfo                              # 内存使用情况
adb shell dumpsys battery                              # 电池状况
adb shell dumpsys window displays                      # 显示屏参数
adb shell dumpsys window | findstr mCurrentFocus       # 显示当前开启窗口名
adb shell "dumpsys window | grep mCurrentFocus"        # 查看前台显示的Activity界面
```

### 5-6. adb shell wm

```bash
adb shell wm size           # 查看屏幕分辨率
adb shell wm size 480x1024  # 将分辨率修改为480px * 1024px
adb shell wm size reset     # 恢复原分辨率
adb shell wm density        # 查看屏幕密度
```

### 5-7. adb shell input

#### 5-7-1. 按键事件
```bash
adb shell input keyevent 3    # HOME键
adb shell input keyevent 4    # 返回键
adb shell input keyevent 24   # 增加音量
adb shell input keyevent 25   # 降低音量
adb shell input keyevent 26   # 电源键
adb shell input keyevent 82   # 菜单键
adb shell input keyevent 224  # 点亮屏幕
adb shell input keyevent 223  # 熄灭屏幕
```

#### 5-7-2. 滑动
```bash
adb shell input swipe 300 1000 300 500  # 滑动（起始x y 结束x y）
```

#### 5-7-3. 输入文本
```bash
adb shell input text hello  # 焦点处于某文本框时输入文本hello
```

#### 5-7-4. 点击
```bash
adb shell input tap 500 1000  # 点击坐标(500, 1000)
```

### 5-12. 截屏

```bash
adb shell screencap -p /sdcard/img.png  # 截图保存在手机设备端
adb pull /sdcard/img.png                # 拷贝到本地
adb exec-out screencap -p > img.png     # 新版本直接截图到本地
```

### 5-13. 录屏

```bash
adb shell screenrecord /sdcard/filename.mp4
```
参数：
- `--size WIDTHxHEIGHT` 视频尺寸
- `--bit-rate RATE` 视频比特率，默认4Mbps
- `--time-limit TIME` 录制时长，单位秒，默认180s

### 5-15. Monkey测试

```bash
adb shell monkey -p <packagename> -v 500  # 向指定应用发送500个伪随机事件
```

## 六、上传、下载文件

```bash
adb push <local> <remote>  # 从本地复制文件到设备
adb pull <remote> <local>  # 从设备复制文件到本地
```

## 七、adb logcat

```bash
adb logcat           # 查看日志
adb logcat -c        # 清除log缓存
adb logcat *:W       # 输出W级别以上的日志
adb logcat ActivityManager:I *:s | findstr "cmp"  # 获取已安装应用Activity类名
```

## 八、其他命令

```bash
adb get-serialno     # 获取序列号
adb bugreport        # 查看bug报告
adb start-server     # 启动adb服务
adb kill-server      # 停止adb服务
adb reboot recovery  # 重启到Recovery模式
adb reboot bootloader # 重启到Fastboot模式
adb root             # 切换到root权限
```

## 常用keycode对照表

| keycode | 功能 |
|---------|------|
| 3 | HOME键 |
| 4 | 返回键 |
| 24 | 增加音量 |
| 25 | 降低音量 |
| 26 | 电源键 |
| 82 | 菜单键 |
| 85 | 播放/暂停 |
| 86 | 停止播放 |
| 87 | 播放下一首 |
| 88 | 播放上一首 |
| 126 | 恢复播放 |
| 127 | 暂停播放 |
| 164 | 静音 |
| 223 | 熄灭屏幕 |
| 224 | 点亮屏幕 |

# 启动第一个qppium服务
appium server --port 4723 --default-capabilities E:\xiaohongshu\xiaohongshuZDH\appium_configs\server1_caps.json --use-drivers uiautomator2 --log ./appium_server1.log --log-level info --address 127.0.0.1

# 启动第二个appium服务
appium server --port 4725 --default-capabilities C:\xiaohongshu\xiaohongshuZDH\appium_configs\server2_caps.json --use-drivers uiautomator2 --log ./appium_server2.log --log-level info --address 127.0.0.1

# 启动第三个appium服务
appium server --port 4727 --default-capabilities C:\xiaohongshu\xiaohongshuZDH\appium_configs\server3_caps.json --use-drivers uiautomator2 --log ./appium_server3.log --log-level info --address 127.0.0.1
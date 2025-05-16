# config/environment.py
import os
from pathlib import Path

class EnvironmentConfig:
    @staticmethod
    def is_docker():
        return os.getenv('RUNNING_MODE') == 'docker'
    
    @staticmethod
    def get_mumu_path():
        if EnvironmentConfig.is_docker():
            # Docker环境下使用映射的路径
            return Path('/mumu/MuMuManager.exe')
        else:
            # 本地环境使用环境变量中的路径
            return Path(os.getenv('MUMU_PATH'))
    
    @staticmethod
    def get_mumu_host():
        if EnvironmentConfig.is_docker():
            # Docker环境下使用host.docker.internal访问宿主机
            return os.getenv('DOCKER_MUMU_HOST', 'host.docker.internal')
        else:
            return 'localhost'

    @staticmethod
    def get_adb_server_host():
        return os.getenv('ADB_SERVER_HOST', 'host.docker.internal')

    @staticmethod
    def get_adb_server_port():
        return os.getenv('ADB_SERVER_PORT', '5037')
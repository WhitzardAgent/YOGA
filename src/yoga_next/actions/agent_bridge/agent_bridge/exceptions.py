"""
自定义异常类
"""


class AgentBridgeError(Exception):
    """基础异常类"""
    pass


class ConnectionError(AgentBridgeError):
    """连接相关异常"""
    pass


class ExecutionError(AgentBridgeError):
    """代码执行异常"""
    pass


class DataSyncError(AgentBridgeError):
    """数据同步异常"""
    pass


class AuthenticationError(AgentBridgeError):
    """认证异常"""
    pass


class TimeoutError(AgentBridgeError):
    """超时异常"""
    pass
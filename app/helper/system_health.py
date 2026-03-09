import psutil
import time
import logging
from datetime import datetime
from threading import Thread
import socket
import platform


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SystemMonitor')


class SystemMonitor:
    
    def __init__(self, check_interval=5):
        
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
        
        # Thresholds for warnings
        self.cpu_threshold = 80.0
        self.memory_threshold = 85.0
        self.disk_threshold = 90.0
        
        # Network stats
        self.last_network_stats = None
        
        logger.info('System Monitor initialized')
    
    def get_system_info(self):
        """Get basic system information"""
        info = {
            'system': platform.system(),
            'node_name': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'hostname': socket.gethostname(),
            'ip_address': socket.gethostbyname(socket.gethostname())
        }
        return info
    
    def get_cpu_info(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
        
        info = {
            'usage_percent': cpu_percent,
            'cores_physical': cpu_count_physical,
            'cores_logical': cpu_count_logical,
            'frequency_current': cpu_freq.current if cpu_freq else 0,
            'frequency_min': cpu_freq.min if cpu_freq else 0,
            'frequency_max': cpu_freq.max if cpu_freq else 0,
            'per_core_usage': cpu_per_core
        }
        
        # Log warning if CPU usage is high
        if cpu_percent > self.cpu_threshold:
            logger.warning(f'High CPU usage detected: {cpu_percent:.1f}%')
        else:
            logger.debug(f'CPU usage: {cpu_percent:.1f}%')
        
        return info
    
    def get_memory_info(self):
        virtual_mem = psutil.virtual_memory()
        swap_mem = psutil.swap_memory()
        
        info = {
            'total': virtual_mem.total,
            'available': virtual_mem.available,
            'used': virtual_mem.used,
            'percent': virtual_mem.percent,
            'free': virtual_mem.free,
            'swap_total': swap_mem.total,
            'swap_used': swap_mem.used,
            'swap_free': swap_mem.free,
            'swap_percent': swap_mem.percent
        }
        
        if virtual_mem.percent > self.memory_threshold:
            logger.warning(f'High memory usage: {virtual_mem.percent:.1f}% '
                         f'({self._bytes_to_gb(virtual_mem.used):.2f}GB used)')
        else:
            logger.debug(f'Memory usage: {virtual_mem.percent:.1f}%')
        
        return info
    
    def get_disk_info(self):
        partitions = psutil.disk_partitions()
        disk_info = []
        
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                info = {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                }
                disk_info.append(info)
                
                if usage.percent > self.disk_threshold:
                    logger.warning(f'High disk usage on {partition.mountpoint}: '
                                 f'{usage.percent:.1f}% ({self._bytes_to_gb(usage.used):.2f}GB used)')
                else:
                    logger.debug(f'Disk {partition.mountpoint}: {usage.percent:.1f}% used')
                    
            except PermissionError:
                continue
        
        disk_io = psutil.disk_io_counters()
        if disk_io:
            info = {
                'read_count': disk_io.read_count,
                'write_count': disk_io.write_count,
                'read_bytes': disk_io.read_bytes,
                'write_bytes': disk_io.write_bytes,
                'read_time': disk_io.read_time,
                'write_time': disk_io.write_time
            }
        
        return disk_info
    
    def get_network_info(self):
        """Get detailed network information"""
        net_io = psutil.net_io_counters()
        
        info = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout,
            'dropin': net_io.dropin,
            'dropout': net_io.dropout
        }
        
        # Calculate transfer rate if we have previous stats
        if self.last_network_stats:
            time_diff = time.time() - self.last_network_stats['timestamp']
            bytes_sent_rate = (net_io.bytes_sent - self.last_network_stats['bytes_sent']) / time_diff
            bytes_recv_rate = (net_io.bytes_recv - self.last_network_stats['bytes_recv']) / time_diff
            
            info['send_rate'] = bytes_sent_rate
            info['recv_rate'] = bytes_recv_rate
            
            # Log network activity
            if bytes_sent_rate > 0 or bytes_recv_rate > 0:
                logger.info(f'Network: ↑ {self._bytes_to_mb(bytes_sent_rate):.2f} MB/s, '
                          f'↓ {self._bytes_to_mb(bytes_recv_rate):.2f} MB/s')
        
        self.last_network_stats = {
            'timestamp': time.time(),
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv
        }
        
        # Network connections
        connections = psutil.net_connections(kind='inet')
        info['active_connections'] = len(connections)
        
        return info
    
    def get_process_info(self, top_n=5):
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'cpu_percent': pinfo['cpu_percent'],
                    'memory_percent': pinfo['memory_percent']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage
        top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:top_n]
        
        # Sort by memory usage
        top_memory = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)[:top_n]
        
        return {
            'total_processes': len(processes),
            'top_cpu': top_cpu,
            'top_memory': top_memory
        }
    
    def get_boot_time(self):
        """Get system boot time"""
        boot_timestamp = psutil.boot_time()
        boot_time = datetime.fromtimestamp(boot_timestamp)
        uptime = datetime.now() - boot_time
        
        return {
            'boot_time': boot_time.strftime('%Y-%m-%d %H:%M:%S'),
            'uptime_seconds': uptime.total_seconds(),
            'uptime_formatted': self._format_uptime(uptime.total_seconds())
        }
    
    
    def get_all_stats(self):
        """Get all system statistics"""
        stats = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'system_info': self.get_system_info(),
            'cpu': self.get_cpu_info(),
            'memory': self.get_memory_info(),
            'disk': self.get_disk_info(),
            'network': self.get_network_info(),
            'processes': self.get_process_info(),
            'boot_info': self.get_boot_time(),
        }
        return stats
    
    def print_stats(self):
        stats = self.get_all_stats()
        
        print("\n" + "="*60)
        print(f"SYSTEM MONITOR - {stats['timestamp']}")
        print("="*60)
        
        # System Info
        sys_info = stats['system_info']
        print(f"\n SYSTEM: {sys_info['system']} {sys_info['release']}")
        print(f"   Hostname: {sys_info['hostname']}")
        print(f"   IP: {sys_info['ip_address']}")
        
        # CPU
        cpu = stats['cpu']
        print(f"\n CPU:")
        print(f"   Usage: {cpu['usage_percent']:.1f}%")
        print(f"   Cores: {cpu['cores_physical']} physical, {cpu['cores_logical']} logical")
        print(f"   Frequency: {cpu['frequency_current']:.0f} MHz")
        
        # Memory
        mem = stats['memory']
        print(f"\n MEMORY:")
        print(f"   Usage: {mem['percent']:.1f}% "
              f"({self._bytes_to_gb(mem['used']):.2f}GB / {self._bytes_to_gb(mem['total']):.2f}GB)")
        print(f"   Available: {self._bytes_to_gb(mem['available']):.2f}GB")
        print(f"   Swap: {mem['swap_percent']:.1f}% "
              f"({self._bytes_to_gb(mem['swap_used']):.2f}GB / {self._bytes_to_gb(mem['swap_total']):.2f}GB)")
        
        # Disk
        print(f"\n DISK:")
        for disk in stats['disk']:
            print(f"   {disk['mountpoint']}: {disk['percent']:.1f}% "
                  f"({self._bytes_to_gb(disk['used']):.2f}GB / {self._bytes_to_gb(disk['total']):.2f}GB)")
        
        # Network
        net = stats['network']
        print(f"\n NETWORK:")
        print(f"   Sent: {self._bytes_to_gb(net['bytes_sent']):.2f}GB")
        print(f"   Received: {self._bytes_to_gb(net['bytes_recv']):.2f}GB")
        print(f"   Active Connections: {net['active_connections']}")
        
        # Processes
        proc = stats['processes']
        print(f"\n  PROCESSES: {proc['total_processes']} total")
        print(f"   Top CPU:")
        for p in proc['top_cpu'][:3]:
            print(f"      {p['name']} (PID {p['pid']}): {p['cpu_percent']:.1f}%")
        
        # Uptime
        boot = stats['boot_info']
        print(f"\n UPTIME: {boot['uptime_formatted']}")

        
        print("="*60 + "\n")
    
    def monitor_continuously(self):
        logger.info('Starting continuous system monitoring...')
        
        while self.running:
            try:
                # Log system stats
                logger.info(f'--- System Check {int(time.time())} ---')
                
                # Get and log stats
                cpu = self.get_cpu_info()
                memory = self.get_memory_info()
                network = self.get_network_info()
                
                # Log summary
                logger.info(f'System Status: CPU {cpu["usage_percent"]:.1f}%, '
                          f'RAM {memory["percent"]:.1f}%, '
                          f'Connections {network["active_connections"]}')
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f'Error in monitoring loop: {str(e)}')
                time.sleep(self.check_interval)
    
    def start(self):
        if not self.running:
            self.running = True
            self.monitor_thread = Thread(target=self.monitor_continuously, daemon=True)
            self.monitor_thread.start()
            logger.info('System monitoring started')
            return True
        return False
    
    def stop(self):
        """Stop monitoring"""
        if self.running:
            self.running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            logger.info('System monitoring stopped')
            return True
        return False
    
    # Helper methods
    def _bytes_to_gb(self, bytes_val):
        return bytes_val / (1024 ** 3)
    
    def _bytes_to_mb(self, bytes_val):
        return bytes_val / (1024 ** 2)
    
    def _format_uptime(self, seconds):
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return " ".join(parts) if parts else "< 1m"


def main():
    print("System Monitor - Real-time System Monitoring")
    print("=" * 60)
    
    monitor = SystemMonitor(check_interval=5)

    try:
        with open('system_stats.log', 'a') as log:
            log.write(f"\n--- System Monitor Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log.write(f"{monitor.get_all_stats()}")


    except:
        print("Warning: Could not write to log file. Logging will be disabled.")
      
    try:
        while True:
            monitor.print_stats()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")





if __name__ == '__main__':
    main()
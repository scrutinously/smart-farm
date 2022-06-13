import subprocess
import json
from dataclasses import dataclass, field, fields
from typing import Any

dev_list = []

@dataclass
class Drive:
    """ Drive and associated SMART Data. I initially made this a dataclass to not need 
    to write an init, but I couldn't get the post_init working properly and ended up
    turning that into an init.

    This creates a Drive object for every drive with the following metrics tracked.
    """
    device: list = field(repr=False)
    dev: str = field(repr=False, init=False, default=None)
    ty: str = field(repr=False, init=False, default=None)
    serial: str = field(repr=False, init=False, default=None)
    model: str = field(repr=False, init=False, default=None)
    ssd: bool = field(repr=False, init=False, default=False)
    blocks: int = field(repr=False, init=False, default=512)

    @dataclass
    class Metric:

        def __init__(self, name: str, value: int):
            self.name = name
            self.value = value

    temp: Metric = field(init=False, default=None)
    hours: Metric = field(init=False, default=None)
    starts: Metric = field(init=False, default=None)
    loads: Metric = field(init=False, default=None)
    read: Metric = field(init=False, default=None)
    write: Metric = field(init=False, default=None)
    readCt: Metric = field(init=False, default=None)
    writeCt: Metric = field(init=False, default=None)
    pctUsed: Metric = field(init=False, default=None)
    realloc: Metric = field(init=False, default=None)
    unErr: Metric = field(init=False, default=None)

    def __init__(self, device: list):
        self.device = device
        self.dev = device[0]
        self.ty = device[1]
        # Splitting SATA and SCSI scrapes due to differences in smartctl output
        if self.ty == 'sat':
            deviceInfo = json.load(subprocess.Popen('smartctl -i --json {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout)
            self.model = deviceInfo["model_name"]
            self.serial = deviceInfo["serial_number"]
            self.blocks = int(deviceInfo["logical_block_size"])
            # devstat page provides better output, but may not work for older drives
            drive = str(subprocess.Popen('smartctl -l devstat {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout.read(), "utf-8").splitlines()
            for entry in drive:
                if entry.startswith('0x'):
                    entry = entry.split()
                    if '0x01' in entry[0]: # Basic stats page
                        if '0x008' in entry[1]:
                            self.starts = self.Metric('starts_stops', int(entry[3]))
                        elif '0x010' in entry[1]:
                            self.hours = self.Metric('power_on_hours', int(entry[3]))
                        elif '0x018' in entry[1]:
                            b = int(entry[3]) * self.blocks
                            self.write = self.Metric('write_bytes', b)
                        elif '0x028' in entry[1]:
                            b = int(entry[3]) * self.blocks
                            self.read = self.Metric('read_bytes', b)
                        elif '0x020' in entry[1]:
                            self.writeCt = self.Metric('write_count', int(entry[3]))
                        elif '0x030' in entry[1]:
                            self.readCt = self.Metric('read_count', int(entry[3]))
                    elif '0x03' in entry[0]: # Spinning mechanism stats page
                        if '0x018' in entry[1]:
                            self.loads = self.Metric('head_loads', int(entry[3]))
                        if '0x020' in entry[1]:
                            self.realloc = self.Metric('reallocated_sectors', int(entry[3]))
                    elif '0x04' in entry[0]: # Error stats page
                        if '0x008' in entry[1]:
                            self.unErr = self.Metric('uncorrectable_errors', int(entry[3]))
                    elif '0x05' in entry[0]: # Temperature stats page
                        if '0x008' in entry[1]:
                            self.temp = self.Metric('temperature', int(entry[3]))
                    elif '0x07' in entry[0]: # SSD stats page
                        if '0x008' in entry[1]:
                            self.pctUsed = self.Metric('percent_used', int(entry[3]))
                            self.ssd = True
            
            """ Old method with json was convenient, but didn't work with all models due to different page layouts
            
            drive = json.load(subprocess.Popen('smartctl -l devstat --json {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout)
            self.temp = self.Metric('temperature', drive["temperature"]["current"])
            self.hours = self.Metric('power_on_hours', drive["power_on_time"]["hours"])
            self.starts = self.Metric('starts_stops', drive["power_cycle_count"])
            sectors = drive["ata_device_statistics"]["pages"][0]["table"][4]["value"]
            b = sectors * 512
            self.read = self.Metric('read_bytes', b)
            sectors = drive["ata_device_statistics"]["pages"][0]["table"][4]["value"]
            b = sectors * 512
            self.write = self.Metric('write_bytes', b) 
            self.readCt = self.Metric('read_count', drive["ata_device_statistics"]["pages"][0]["table"][5]["value"])
            self.writeCt = self.Metric('write_count', drive["ata_device_statistics"]["pages"][0]["table"][3]["value"])
            try:
                self.loads = self.Metric('head_loads', drive["ata_device_statistics"]["pages"][1]["table"][2]["value"])
            except IndexError:
                if drive["ata_device_statistics"]["pages"][4]["table"][0]["name"] and 'Percentage Used' in drive["ata_device_statistics"]["pages"][4]["table"][0]["name"]:
                    self.pctUsed = self.Metric('percent_used', drive["ata_device_statistics"]["pages"][4]["table"][0]["value"])
                    self.ssd = True
            """

        elif self.ty == 'scsi':
            deviceInfo = json.load(subprocess.Popen('smartctl -i --json {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout)
            # This try line is directly thanks to Seagate using "scsi_product" instead of "product for model
            try:
                self.model = deviceInfo["product"]
            except:
                try:
                    self.model = deviceInfo["scsi_product"]
                except KeyError: # In case any other brands use another key name, will leave default None
                    pass
            self.serial = deviceInfo["serial_number"]
            self.blocks = deviceInfo["logical_block_size"]
            drive = str(subprocess.Popen('smartctl -a {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout.read(), "utf-8").splitlines()
            for entry in drive:
                entry = entry.split(':')
                if 'Current' in entry[0]:
                    entry[1] = entry[1].strip().strip('C')
                    self.temp = self.Metric('temperature', int(entry[1]))
                elif 'Accumulated' in entry[0]:
                    if 'power on' in entry[0]:
                        entry[1] = entry[1].strip('minutes ')
                        self.hours = self.Metric('power_on_hours', int(entry[1]))
                    elif 'start-stop' in entry[0]:
                        self.starts = self.Metric('starts_stops', int(entry[1]))
                    elif 'load-unload' in entry[0]:
                        self.loads = self.Metric('head_loads', int(entry[1]))
                elif 'Percentage' in entry[0]:
                    self.pctUsed = self.Metric('percent_used', entry[1].strip('%'))
                    self.ssd = True
                elif 'Elements in grown defect list' in entry[0]:
                    self.realloc = self.Metric('reallocated_sectors', int(entry[1]))
            for rw in drive: # Required different var due to some differences in model info layouts including multiple "read/write" entries
                if rw.startswith('read:'):
                    b = int(float(rw.split()[6]) * 1024 * 1024 * 1024)
                    self.read = self.Metric('read_bytes', b)
                elif rw.startswith('write:'):
                    b = int(float(rw.split()[6]) * 1024 * 1024 * 1024)
                    self.write = self.Metric('write_bytes', b)

        elif self.ty == 'nvme':
            self.ssd = True
            deviceInfo = json.load(subprocess.Popen('smartctl -i --json {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout)
            try:
                self.model = deviceInfo["model_name"]
            except KeyError:
                pass
            self.serial = deviceInfo["serial_number"]
            self.blocks = deviceInfo["logical_block_size"]
            drive = str(subprocess.Popen('smartctl -A {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout.read(), "utf-8").splitlines()
            # This may not work for many drives, I only have samsung NVMes to test and other brands may format output differently
            drive = json.load(subprocess.Popen('smartctl -A --json {}'.format(self.dev), shell=True, stdout=subprocess.PIPE).stdout)
            self.temp = self.Metric('temperature', drive["temperature"]["current"])
            self.hours = self.Metric('power_on_hours', drive["power_on_time"]["hours"])
            self.starts = self.Metric('starts_stops', drive["power_cycle_count"])
            try:
                self.pctUsed = self.Metric('percent_used', drive["nvme_smart_health_information_log"]["percentage_used"])
            except KeyError:
                pass
            try:
                b = drive["nvme_smart_health_information_log"]["data_units_read"] * self.blocks
                self.read = self.Metric('read_bytes', b)
            except KeyError:
                pass
            try:
                b = drive["nvme_smart_health_information_log"]["data_units_written"] * self.blocks
                self.write = self.Metric('write_bytes', b)
            except KeyError:
                pass
            try:
                self.readCt = self.Metric('read_count', drive["nvme_smart_health_information_log"]["host_reads"])
            except KeyError:
                pass
            try:
                self.writeCt = self.Metric('write_count', drive["nvme_smart_health_information_log"]["host_writes"])
            except KeyError:
                pass
            try:
                self.unErr = self.Metric('uncorrectable_errors', drive["nvme_smart_health_information_log"]["critical_warning"])
            except KeyError:
                pass
    """ This iter was mainly used for testing, but it could be handy, 
    returns only Metric object data and not the label items when looped
    through a Drive object.
    """
    def __iter__(self):
        for item in self.__dict__.values():
            if type(item) is Drive.Metric:
                yield item

    # Generates the node-exporter label
    def label(self):
        return 'device="{0}",type="{1}",serial="{2}",model="{3}",ssd="{4}"'.format(self.device[0],self.device[1],self.serial,self.model,self.ssd)

    # Returns the name from the Metric object currently being scraped
    def metric_name(self, metric):
        if getattr(self, metric) is not None:
            return getattr(self, metric).name

    # Returns the value from the Metric object currently being scraped
    def metric_value(self, metric):
        if getattr(self, metric) is not None:
            return getattr(self, metric).value

    # Formats the output for node-exporter
    def metric_format(self, prefix, metric):
        return '{0}_{1}{{{2}}} {3}'.format(prefix, self.metric.name, self.label(), self.metric.value)

# Creates a list of all disks, then creates a Drive object for each one
def get_disks():
    disks = str(subprocess.Popen("smartctl --scan-open", shell=True, stdout=subprocess.PIPE).stdout.read(), "utf-8").splitlines()
    for disk in disks:
        disk = disk.split(' ')
        device = [disk[0], disk[2]]
        dev = disk[0].split('/')[2]
        locals()[dev] = Drive(device)
        dev_list.append(locals()[dev])

metric_list = {
        'temp': 'temperature',
        'hours': 'power_on_hours',
        'starts': 'starts_stops',
        'loads': 'head_loads',
        'read': 'read_bytes',
        'write': 'write_bytes',
        'readCt': 'read_count',
        'writeCt': 'write_count',
        'pctUsed': 'percent_used',
        'realloc': 'reallocated_sectors',
        'unErr': 'uncorrectable_errors'
        }

prefix = 'farm' # prefix to appear in front of all metrics, change to whatever is desired

# Formats and prints the node-exporter HELP and TYPE lines
def metric_help_type(prefix, metric):
    print('# HELP {0}_{1} SMART'.format(prefix,metric))
    print('# TYPE {0}_{1} gauge'.format(prefix,metric))

# Same as above, but not in the Drive object, ended up using this one
def metric_format(prefix, metric, value, label):
    return '{0}_{1}{{{2}}} {3}'.format(prefix, metric, label, value)

def main():
    get_disks()
    for key, val in metric_list.items():
        metric_help_type(prefix, val) # Sets the name for each metric in node-exporter 
        for item in dev_list:
            if getattr(item, key) is not None:
                print(metric_format(prefix ,item.metric_name(key),item.metric_value(key),item.label()))
    # As I'm writing this comment I realize I didn't need a Metric object, I could have simply used the val variable
    # from above to take care of the "metric_value" variable, but I designed the script as focused on the Drive object
    # rather than focused on printing out metrics.

if __name__ == '__main__':
    main()

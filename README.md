# SMART-farm
Basic smartmontools scrape and exporter for Prometheus node-exporter.

Grafana Dashboard:

![dashboard screenshot](https://github.com/scrutinously/smart-farm/blob/main/smart-farm_dash.png?raw=true)

## Usage
Simply run the script with elevated priveleges and direct the output to a file that can be scraped by node-exporter:

```sudo python smart.py > /var/lib/node-exporter/smart-farm.prom```

The process can be automated using a systemd timer and unit, examples are included. The systemd unit will have to be customized to fit your needs and file paths.

Also included is a grafana dashboard for my currently monitored stats. If there are any additional SMART stats that you would like to see, make a PR or an issue and let me know (any tips on improving the code are also welcome).

I have tested the script on older Seagate SAS drives, newer WD SAS drives, a mix of WD, Seagate, and Toshiba SATA drives. I currently do not have any USB drives to test with, so I do not know if it will scrape them or not.


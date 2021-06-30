# Self Delegator Bot

A simple delf delegator bot for Desmos Blockchain

## Requirements

* Desmos CLI
* Python >= 3

## 1\. Install

``` bash
git clone https://github.com/g-luca/selfdeleg.git && cd selfdeleg && mkdir logs
```

## 2\. Configure

``` bash
mv template.ini config.ini && nano config.ini
```

And edit:

1. `KEY_NAME` with your validator key name, and `KEY_BACKEND` if you use a different [keyring backend](https://docs.cosmos.network/v0.42/run-node/keyring.html)
2. `VALIDATOR_ADDRES`, `USER_ADDRES`, `DELEGATE_ADDRESS`, with your addresses.
If you want to self delegate, `USER_ADDRES` and `DELEGATE_ADDRESS` should match.
3. If you are installing the bot in a machine that is not running a node/validator configure `DEFAULT_NODE_ADDRESS` and `DEFAULT_NODE_PORT` with remote nodes addresses
4. `MINIMUM_BALANCE` amount of DARIC that the bot will always keep (minimum 1 DARIC)
5. The other configuration values are optional

## 3\. Run

``` bash
python3 bot.py
```

## 3\. Run as a Service \(Ubuntu\)
<br>
``` bash
sudo nano /etc/systemd/system/selfdeleg.service
```

and paste:

````
[Unit]
Description=Desmos Self Delegator Bot
After=multi-user.target


[Service]
WorkingDirectory=/home/ubuntu/selfdeleg/
User=ubuntu
Type=simple
Restart=always

Environment="PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/bin/bash /home/ubuntu/selfdeleg/start.sh


[Install]
WantedBy=multi-user.target
````
<br>
Then,

``` bash
sudo systemctl daemon-reload
```
<br>
``` bash
sudo systemctl start selfdeleg.service
```
<br>
To follow the output:
<br>
``` bash
tail -f ./logs/debug.log
```
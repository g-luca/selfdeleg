import subprocess
import os
import json
import time
from datetime import datetime
import socket
import configparser
import asyncio
import logging
import logging.handlers as handlers
import getpass
import pexpect
import sys
logger = logging.getLogger('valcontrol')
logger.setLevel(logging.DEBUG)
logHandler = handlers.TimedRotatingFileHandler(
    'logs/debug.log', when='midnight', interval=1)
logHandler.suffix = "%Y-%m-%d"
logHandler.setLevel(logging.DEBUG)
logger.addHandler(logHandler)
config = configparser.ConfigParser()
config.read("config.ini")
DEBUG_WATCH_ONLY = int(config["Debug"]["DEBUG_WATCH_ONLY"])
# Validator settings
USER_ADDRESS = str(config["Validator"]["USER_ADDRESS"])
VALIDATOR_ADDRESS = str(config["Validator"]["VALIDATOR_ADDRESS"])
DELEGATE_ADDRESS = str(config["Validator"]["DELEGATE_ADDRESS"])
REDELEGATE_AT = float(config["Validator"]["REDELEGATE_AT"])
TRANSACTION_FEES = str(config["Validator"]["TRANSACTION_FEES"])
MINIMUM_BALANCE = float(config["Validator"]["MINIMUM_BALANCE"])
KEY_NAME = str(config["Validator"]["KEY_NAME"])
KEY_BACKEND = str(config["Validator"]["KEY_BACKEND"])
CHAIN_ID = str(config["Validator"]["CHAIN_ID"])
DEFAULT_NODE_ADDRESS = str(config["Validator"]["DEFAULT_NODE_ADDRESS"])
DEFAULT_NODE_PORT = str(config["Validator"]["DEFAULT_NODE_PORT"])
DEFAULT_NODE = str(DEFAULT_NODE_ADDRESS + ":" + DEFAULT_NODE_PORT)

COIN_DENOM = str(config["Validator"]["COIN_DENOM"])
UCOIN_DENOM = str(config["Validator"]["UCOIN_DENOM"])

REFRESH_MINUTES = float(config["Validator"]["REFRESH_MINUTES"])
# ----------------------
# Command Balance
COMMAND_GET_BALANCE = 'desmos q bank balances {} --node {} -o json'.format(
    USER_ADDRESS, DEFAULT_NODE).split(" ")
# Command Redelegate
COMMAND_REDELEGATE = 'desmos tx staking delegate {} --from {} --keyring-backend {} REPLACE_AMOUNT --fees {} --gas="auto" --node {} --chain-id {} --yes -o json --broadcast-mode block --gas 250000'.format(
    VALIDATOR_ADDRESS, KEY_NAME, KEY_BACKEND, TRANSACTION_FEES, DEFAULT_NODE, CHAIN_ID)
# Command Rewards
COMMAND_GET_REWARDS_BALANCE = 'desmos q distribution rewards {} {} -o json --node {}'.format(
    USER_ADDRESS, VALIDATOR_ADDRESS, DEFAULT_NODE).split(" ")
COMMAND_WITHDRAW_REWARDS = 'desmos tx distribution withdraw-rewards {} --commission --from {} --keyring-backend {} --fees {} --gas="auto" --chain-id {} --node {} --yes -o json --broadcast-mode block --gas 250000'.format(
    VALIDATOR_ADDRESS, KEY_NAME, KEY_BACKEND, TRANSACTION_FEES, CHAIN_ID, DEFAULT_NODE)
# Command Commissions
COMMAND_GET_COMMISSION_BALANCE = 'desmos q distribution commission {} -o json --node {}'.format(
    VALIDATOR_ADDRESS, DEFAULT_NODE).split(" ")
# --------------------------


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
# Execute a shell commands array (for desmos cli)


def cmd(cmds):
    try:
        proc = subprocess.Popen(
            cmds, shell=False,  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        return stdout
    except:
        print("command error")
        return False

# Check if the transaction was successful
def read_tx_success(tx_result):
    print(tx_result)
    # code = 0 means tx success
    if '"code":0' in str(tx_result):
        return True
    else:
        print("read tx result error")
        return False

# Perform a transaction
def tx(cmd, password):
    try:
        child = pexpect.spawn(cmd, timeout=10)
        child.expect('.*')
        success = read_tx_success(child.read())
        if not success:
            child.sendline(password)
            child.expect('.*')
            time.sleep(6)
            success = read_tx_success(child.read())
        child.close()
        return success

    except:
        print("tx error")
        return False


class Desmosbot:
    started_at = datetime.now()
    total_redelegated = 0
    password = ""
    balance = 0
    reward = 0
    commission = 0
    UCOIN = 1000000

    def __init__(self, password):
        self.password = password
        self.update()

    def confirmWithPassword(self):
        cmd("echo " + self.password)

    def updateBalance(self):
        try:
            balance_raw = cmd(COMMAND_GET_BALANCE)
            balance = json.loads(balance_raw)
            amount = float(
                balance['balances'][0]['amount']) / self.UCOIN
            self.balance = float(amount)
            return True
        except:
            print("Error updating balance")
            return False

    def updateValidatorReward(self):
        try:
            reward_balance_raw = cmd(COMMAND_GET_REWARDS_BALANCE)
            reward_balance = json.loads(reward_balance_raw)
            reward_amount = float(
                reward_balance['rewards'][0]['amount']) / self.UCOIN
            self.reward = float(reward_amount)
            return True
        except:
            print("Error updating rewards")
            return False

    def updateValidatorCommission(self):
        try:
            commission_balance_raw = cmd(COMMAND_GET_COMMISSION_BALANCE)
            commission_balance = json.loads(commission_balance_raw)
            commission_amount = float(
                commission_balance['commission'][0]['amount']) / self.UCOIN
            self.commission = float(commission_amount)
            return True
        except:
            print("Error updating commissions")
            return False

    def update(self):
        sB = self.updateBalance()
        sR = self.updateValidatorReward()
        sC = self.updateValidatorCommission()
        return sB and sR and sC
    # REWARDS

    def withdrawRewards(self):
        if(self.reward >= REDELEGATE_AT):
            print()
            tx_success = self.tx_withdrawRewards()
            if(tx_success):
                return self.reward
        else:
            print(" > rewards under " + str(REDELEGATE_AT) + " " + COIN_DENOM)
        return 0
    # REDELEGATION LOGIC

    def redelegate(self):
        now = str(datetime.now()) + ":"
        total_rewards_withdrawn: float = 0
        # Withdraw commission and rewards
        if(self.commission + self.reward >= REDELEGATE_AT and not DEBUG_WATCH_ONLY):
            success = self.tx_withdrawRewards()
            if(success):
                total_rewards_withdrawn = self.commission + self.reward
                logger.info(now+"Withdrwawn Rewards and Commissions for " +
                            str(total_rewards_withdrawn) + COIN_DENOM)
        amount_to_redelegate: float = float(
            self.balance) + float(total_rewards_withdrawn) - float(MINIMUM_BALANCE)
        if(amount_to_redelegate >= float(REDELEGATE_AT)):
            if (not DEBUG_WATCH_ONLY):
                self.tx_redelegate(amount_to_redelegate)
            self.total_redelegated += amount_to_redelegate
            logger.info(now+"Redelegated " +
                        str(self.total_redelegated) + COIN_DENOM)
        else:
            print("Rewards and Commissions under " +
                  str(REDELEGATE_AT) + " " + COIN_DENOM)
    # REDELEGATING TRANSACTION

    def tx_redelegate(self, amount_in_daric: float):
        print(bcolors.WARNING + "Redelegating..." + bcolors.ENDC)
        amount_str = str(amount_in_daric * self.UCOIN) + UCOIN_DENOM
        cmdRedelegate = COMMAND_REDELEGATE.replace(
            'REPLACE_AMOUNT', amount_str)
        redelegate_success = tx(
            cmdRedelegate, self.password)
        return redelegate_success
    # WITHDRAW REWARDS TRANSACTION

    def tx_withdrawRewards(self):
        print(bcolors.WARNING + "Withdrawing rewards..." + bcolors.ENDC)
        print(COMMAND_WITHDRAW_REWARDS)
        withdraw_success = tx(
            COMMAND_WITHDRAW_REWARDS, self.password)
        return withdraw_success


async def main():
    os.system("clear")
    password = ""
    try:
        password = sys.argv[1]
    except:
        password = getpass.getpass("Keyring password:")
    print("starting...")
    if(MINIMUM_BALANCE < 1):
        print("\n\n Configuration MINIMUM_BALANCE MUST BE > 1 !!!\n\n")
        raise "MINIMUM_BALANCE ERROR"
    bot = Desmosbot(password)
    while(True):
        os.system("clear")
        now = datetime.now()
        print("Started at: " + bcolors.OKCYAN +
              bot.started_at.strftime("%H:%M:%S") + bcolors.ENDC)
        print("Total Redelegations: " + bcolors.OKGREEN +
              str(bot.total_redelegated) + " " + COIN_DENOM + bcolors.ENDC)
        print("\nLast update: " + bcolors.OKCYAN +
              now.strftime("%H:%M:%S") + bcolors.ENDC)
        print("\n"+bcolors.OKGREEN + "Balance: " +
              bcolors.ENDC + str(bot.balance) + " " + COIN_DENOM)
        print(bcolors.OKGREEN + "Reward: " +
              bcolors.ENDC + str(bot.reward) + " " + COIN_DENOM)
        print(bcolors.OKGREEN + "Commissions: " +
              bcolors.ENDC + str(bot.commission) + " " + COIN_DENOM)
        while True:
            updateSuccess = bot.update()  # update balance, commissions, rewards
            if(updateSuccess):
                bot.redelegate()  # withdraw rewards and redelegate
                break
            else:
                print("New attempt to update balances")
                time.sleep(10)
        print(bcolors.OKCYAN +
              "\n\nSleeping... ({}m)".format(REFRESH_MINUTES) + bcolors.ENDC)
        time.sleep(REFRESH_MINUTES * 60)
        os.system("clear")
asyncio.run(main())

import sys
from StringIO import StringIO
from paramiko import SSHClient, AutoAddPolicy, RSAKey

from cloudshell.cm.customscript.domain.reservation_output_writer import ReservationOutputWriter
from cloudshell.cm.customscript.domain.script_configuration import HostConfiguration
from cloudshell.cm.customscript.domain.script_executor import IScriptExecutor, ErrorMsg
from cloudshell.cm.customscript.domain.script_file import ScriptFile


class LinuxScriptExecutor(IScriptExecutor):
    class ExecutionResult(object):
        def __init__(self, exit_code, std_out, std_err):
            self.std_err = std_err
            self.std_out = std_out
            self.success = exit_code == 0

    def __init__(self, logger, target_host):
        """
        :type logger: Logger
        :type target_host: HostConfiguration
        """
        self.logger = logger
        self.session = SSHClient()
        self.session.set_missing_host_key_policy(AutoAddPolicy())
        if target_host.access_key:
            key_stream = StringIO(target_host.access_key)
            key_obj = RSAKey.from_private_key(key_stream)
            self.session.connect(target_host.ip, pkey=key_obj)
        else:
            self.session.connect(target_host.ip, username=target_host.username, password=target_host.password)

    def create_temp_folder(self):
        """
        :rtype str
        """
        result = self._run('mktemp -d')
        if not result.success:
            raise Exception(ErrorMsg.CREATE_TEMP_FOLDER % result.std_err)
        return result.std_out

    def copy_script(self, tmp_folder, script_file):
        """
        :type tmp_folder: str
        :type script_file: ScriptFile
        """
        sftp = None
        try:
            sftp = self.session.open_sftp()
            file_stream = StringIO(script_file.text)
            sftp.putfo(file_stream, tmp_folder+'/'+script_file.name)
        except IOError as e:
            raise Exception,ErrorMsg.COPY_SCRIPT % str(e),sys.exc_info()[2]
        finally:
            if sftp:
                sftp.close()

    def run_script(self, tmp_folder, script_file, output_writer):
        """
        :type tmp_folder: str
        :type script_file: ScriptFile
        :type output_writer: ReservationOutputWriter
        """
        result = self._run('sh '+tmp_folder+'/'+script_file.name)
        output_writer.write(result.std_out)
        output_writer.write(result.std_err)
        if not result.success:
            raise Exception(ErrorMsg.RUN_SCRIPT % result.std_err)

    def delete_temp_folder(self, tmp_folder):
        """
        :type tmp_folder: str
        """
        result = self._run('rm -rf '+tmp_folder)
        if not result.success:
            raise Exception(ErrorMsg.DELETE_TEMP_FOLDER % result.std_err)

    def _run(self, txt, *args):
        code = txt % args
        self.logger.debug('BashScript:' + code)
        stdin, stdout, stderr = self.session.exec_command(code)
        exit_code = stdout.channel.recv_exit_status()
        stdout_txt = ''.join(stdout.readlines())
        stderr_txt = ''.join(stderr.readlines())
        self.logger.debug('ReturnedCode:' + str(exit_code))
        self.logger.debug('Stdout:' + stdout_txt)
        self.logger.debug('Stderr:' + stderr_txt)
        return LinuxScriptExecutor.ExecutionResult(exit_code, stdout_txt, stderr_txt)
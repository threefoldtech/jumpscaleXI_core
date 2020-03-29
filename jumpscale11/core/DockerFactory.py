class DockerFactory:
    _init = False
    _dockers = {}
    _j = None

    @staticmethod
    def indocker():
        """
        will check if we are in a docker
        :return:
        """
        rc, out, _ = j.core.tools.execute("cat /proc/1/cgroup", die=False, showout=False)
        if rc == 0 and out.find("/docker/") != -1:
            return True
        return False

    @staticmethod
    def init(name=None):
        if not DockerFactory._init:
            rc, out, _ = j.core.tools.execute("cat /proc/1/cgroup", die=False, showout=False)
            if rc == 0 and out.find("/docker/") != -1:
                # nothing to do we are in docker already
                return

            j.core.myenv.init()

            if MyEnvplatform == "linux" and not j.core.tools.cmd_installed("docker"):
                UbuntuInstaller.docker_install()
                j.core.myenv._cmd_installed["docker"] = shutil.which("docker")

            if not j.core.tools.cmd_installed("docker"):
                raise j.exceptions.Operations("Could not find Docker installed")

            DockerFactory._init = True
            cdir = j.data.text.replace("{DIR_BASE}/var/containers")
            j.core.tools.dir_ensure(cdir)
            for name_found in os.listdir(cdir):
                if not os.path.isdir(os.path.join(cdir, name_found)):
                    # https://github.com/threefoldtech/jumpscaleX_core/issues/297
                    # in case .DS_Store is created when opened in finder
                    continue
                # to make sure there is no recursive behaviour if called from a docker container
                if name_found != name and name_found.strip().lower() not in ["shared"]:
                    DockerContainer(name_found)

    @staticmethod
    def container_get(name, image="threefoldtech/3bot2", start=False, delete=False, ports=None, mount=True):
        DockerFactory.init()
        if delete and name in DockerFactory._dockers:
            docker = DockerFactory._dockers[name]
            docker.delete()
            # needed because docker object is being retained
            docker.config.save()
            DockerFactory._dockers.pop(name)

        docker = None
        if name in DockerFactory._dockers:
            docker = DockerFactory._dockers[name]
            if docker.container_running:
                if mount:
                    if docker.info["Mounts"] == []:
                        # means the current docker has not been mounted
                        docker.stop()
                        docker.start(mount=True)
                else:
                    if docker.info["Mounts"] != []:
                        docker.stop()
                        docker.start(mount=False)
                return docker
        if not docker:
            docker = DockerContainer(name=name, image=image, delete=delete, ports=ports)
        if start:
            docker.start(mount=mount)
        return docker

    @staticmethod
    def containers_running():
        names = j.core.tools.execute("docker ps --format='{{json .Names}}'", showout=False, replace=False)[1].split("\n")
        names = [i.strip("\"'") for i in names if i.strip() != ""]
        return names

    @staticmethod
    def containers_names():
        names = j.core.tools.execute("docker container ls -a --format='{{json .Names}}'", showout=False, replace=False)[
            1
        ].split("\n")
        names = [i.strip("\"'") for i in names if i.strip() != ""]
        return names

    @staticmethod
    def containers():
        DockerFactory.init()
        return DockerFactory._dockers.values()

    @staticmethod
    def list():
        res = []
        for d in DockerFactory.containers():
            print(" - %-10s : %-15s : %-25s (sshport:%s)" % (d.name, d.config.ipaddr, d.config.image, d.config.sshport))
            res.append(d.name)
        return res

    @staticmethod
    def container_name_exists(name):
        return name in DockerFactory.containers_names()

    @staticmethod
    def image_names():
        names = j.core.tools.execute("docker images --format='{{.Repository}}:{{.Tag}}'", showout=False, replace=False)[
            1
        ].split("\n")
        res = []
        for name in names:
            name = name.strip()
            name = name.strip("\"'")
            name = name.strip("\"'")
            if name == "":
                continue
            if ":" in name:
                name = name.split(":", 1)[0]
            res.append(name)

        return res

    @staticmethod
    def image_name_exists(name):
        if ":" in name:
            name = name.split(":")[0]
        return name in DockerFactory.image_names()

    @staticmethod
    def image_remove(name):
        if name in DockerFactory.image_names():
            j.core.tools.log("remove container:%s" % name)
            j.core.tools.execute("docker rmi -f %s" % name)

    @staticmethod
    def reset(images=True):
        """
        jsx containers-reset

        will stop/remove all containers
        if images==True will also stop/remove all images
        :return:
        """
        for name in DockerFactory.containers_names():
            d = DockerFactory.container_get(name)
            d.delete()

        # will get all images based on id
        names = j.core.tools.execute("docker images --format='{{.ID}}'", showout=False, replace=False)[1].split("\n")
        for image_id in names:
            if image_id:
                j.core.tools.execute("docker rmi -f %s" % image_id)

        j.core.tools.delete(j.data.text.replace("{DIR_BASE}/var/containers"))

    # @staticmethod
    # def get_container_port_binding(container_name="3obt", port="9001/udp"):
    #     ports_bindings = j.core.tools.execute(
    #         "docker inspect {container_name} --format={data}".format(
    #             container_name=container_name, data="'{{json .HostConfig.PortBindings}}'"
    #         ),
    #         showout=False,
    #         replace=False,
    #     )
    #     # Get and serialize the binding ports data
    #     all_ports_data = json.loads(ports_bindings[1])
    #     port_binding_data = all_ports_data.get(port, None)
    #     if not port_binding_data:
    #         raise j.exceptions.Input(
    #             f"Error happened during parsing the binding ports data from container {conitainer_name} and port {port}"
    #         )
    #
    #     host_port = port_binding_data[-1].get("HostPort")
    #     return host_port

    # @staticmethod
    # def container_running_with_udp_ports_wireguard():
    #     containers_ports = dict()
    #     containers_names = DockerFactory.containers_names()
    #     for name in containers_names:
    #         port_binding = DockerFactory.get_container_port_binding(container_name=name, port="9001/udp")
    #         containers_ports[name] = port_binding
    #     return containers_ports

    @staticmethod
    def get_container_ip_address(container_name="3bot"):
        container_ip = j.core.tools.execute(
            "docker inspect {container_name} --format={data}".format(
                container_name=container_name, data="'{{json .NetworkSettings.Networks.bridge.IPAddress}}'"
            ),
            showout=False,
            replace=False,
        )[1].split("\n")
        if not container_ip:
            raise j.exceptions.Input(
                f"Error happened during parsing the container {conitainer_name} ip address data "
            )
        # Get the data in the required format
        formatted_container_ip = container_ip[0].strip("\"'")
        return formatted_container_ip

    @staticmethod
    def containers_running_ip_address():
        containers_ip_addresses = dict()
        containers_names = DockerFactory.containers_names()
        for name in containers_names:
            container_ip = DockerFactory.get_container_ip_address(container_name=name)
            containers_ip_addresses[name] = container_ip
        return containers_ip_addresses


class DockerConfig:
    def __init__(self, name, image=None, startupcmd=None, delete=False, ports=None):
        """
        port config is as follows:

        start_range = 9000+portrange*10
        ssh = start_range
        wireguard = start_range + 1

        :param name:
        :param portrange:
        :param image:
        :param startupcmd:
        """
        self.name = name
        self.ports = ports

        self.path_vardir = j.data.text.replace("{DIR_BASE}/var/containers/{NAME}", args={"NAME": name})
        j.core.tools.dir_ensure(self.path_vardir)
        self.path_config = "%s/docker_config.toml" % (self.path_vardir)
        # self.wireguard_pubkey

        if delete:
            j.core.tools.delete(self.path_vardir)

        if not j.core.tools.exists(self.path_config):

            self.portrange = None

            if image:
                self.image = image
            else:
                self.image = "threefoldtech/3bot2"

            if startupcmd:
                self.startupcmd = startupcmd
            else:
                self.startupcmd = "/sbin/my_init"

        else:
            self.load()

        self.ipaddr = "localhost"  # for now no ipaddr in wireguard

    def _find_port_range(self):
        existingports = []
        for container in DockerFactory.containers():
            if container.name == self.name:
                continue
            if not container.config.portrange in existingports:
                existingports.append(container.config.portrange)

        for i in range(50):
            if i in existingports:
                continue
            port_to_check = 9000 + i * 10
            if not j.core.tools.tcp_port_connection_test(ipaddr="localhost", port=port_to_check):
                self.portrange = i
                print(" - SSH PORT ON: %s" % port_to_check)
                return
        if not self.portrange:
            raise j.exceptions.Input("cannot find tcp port range for docker")
        self.sshport = 9000 + int(self.portrange) * 10

    def reset(self):
        """
        erase the past config
        :return:
        """
        j.core.tools.delete(self.path_vardir)
        self.load()

    def done_get(self, name):
        name2 = "done_%s" % name
        if name2 not in self.__dict__:
            self.__dict__[name2] = False
            self.save()
        return self.__dict__[name2]

    def done_set(self, name):
        name2 = "done_%s" % name
        self.__dict__[name2] = True
        self.save()

    def done_reset(self, name=None):
        if not name:
            ks = [str(k) for k in self.__dict__.keys()]
            for name in ks:
                if name.startswith("done_"):
                    self.__dict__.pop(name)
        else:
            if name.startswith("done_"):
                name = name[5:]
            name2 = "done_%s" % name
            self.__dict__[name2] = False
            self.save()

    def val_get(self, name):
        if name not in self.__dict__:
            self.__dict__[name] = None
            self.save()
        return self.__dict__[name]

    def val_set(self, name, val=None):
        self.__dict__[name] = val
        self.save()

    def load(self):
        if not j.core.tools.exists(self.path_config):
            raise j.exceptions.JSBUG("could not find config path for container:%s" % self.path_config)

        r = j.core.tools.config_load(self.path_config, keys_lower=True)
        ports = r.pop("ports", None)
        if ports:
            self.ports = json.loads(ports)
        if r != {}:
            self.__dict__.update(r)

        assert isinstance(self.portrange, int)

        a = 9005 + int(self.portrange) * 10
        b = 9009 + int(self.portrange) * 10
        udp = 9001 + int(self.portrange) * 10
        ssh = 9000 + int(self.portrange) * 10
        http = 7000 + int(self.portrange) * 10
        self.sshport = ssh
        self.portrange_txt = "-p %s-%s:8005-8009" % (a, b)
        self.portrange_txt = "-p %s:80" % http
        self.portrange_txt += " -p %s:9001/udp" % udp
        self.portrange_txt += " -p %s:22" % ssh

    @property
    def ports_txt(self):
        txt = ""
        if self.portrange_txt:
            txt = self.portrange_txt
        if self.ports:
            for key, value in self.ports.items():
                txt += f" -p {key}:{value}"
        return txt

    def save(self):
        data = self.__dict__.copy()
        data["ports"] = json.dumps(data["ports"])
        j.core.tools.config_save(self.path_config, data)
        assert isinstance(self.portrange, int)
        self.load()

    def __str__(self):
        return str(self.__dict__)

    __repr__ = __str__


class DockerContainer:
    def __init__(self, name="default", delete=False, image=None, startupcmd=None, ports=None):
        """
        if you want to start from scratch use: "phusion/baseimage:master"

        if codedir not specified will use {DIR_BASE}/code
        """
        if name == "shared":
            raise j.exceptions.JSBUG("should never be the shared obj")
        if not DockerFactory._init:
            raise j.exceptions.JSBUG("make sure to call DockerFactory.init() bedore getting a container")

        DockerFactory._dockers[name] = self

        self.config = DockerConfig(name=name, image=image, startupcmd=startupcmd, delete=delete, ports=ports)

        if self.config.portrange is None:
            self.config._find_port_range()
            self.config.save()

        if delete:
            self.delete()

            self.config.save()

        if "SSH_Agent" in j.core.myenv.config and j.core.myenv.config["SSH_Agent"]:
            j.core.myenv.sshagent.key_default_name  # means we will load ssh-agent and help user to load it properly

        if len(j.core.myenv.sshagent.keys_list()) == 0:
            raise j.exceptions.Base("Please load your ssh-agent with a key!")

        self._wireguard = None
        self._executor = None

    def done_get(self, name):
        name = name.strip().lower()
        path = "/root/state/%s" % name
        try:
            self.dexec("cat %s" % path)
        except:
            return False
        return True

    def done_set(self, name):
        name = name.strip().lower()
        path = "/root/state/%s" % name
        self.dexec("touch %s" % path)

    def done_reset(self, name=None):
        if not name:
            self.dexec("rm -rf /root/state")
            self.dexec("mkdir -p /root/state")
        else:
            name = name.strip().lower()
            path = "/root/state/%s" % name
            self.dexec("rm -f %s" % path)

    @property
    def executor(self):
        if not self._executor:
            self._executor = ExecutorSSH(
                addr=self.config.ipaddr, port=self.config.sshport, debug=False, name=self.config.name
            )
        return self._executor

    @property
    def container_exists_config(self):
        """
        returns True if the container is defined on the filesystem with the config file
        :return:
        """
        if j.core.tools.exists(self._path):
            return True

    @property
    def mount_code_exists(self):
        m = self.info["Mounts"]
        for item in m:
            if item["Destination"] == "/sandbox/code":
                return True
        return False

    @property
    def container_exists_in_docker(self):
        return self.name in DockerFactory.containers_names()

    @property
    def container_running(self):
        return self.name in DockerFactory.containers_running()

    @property
    def _path(self):
        return self.config.path_vardir

    @property
    def image(self):
        return self.config.image

    @image.setter
    def image(self, val):
        val = self._image_clean(val)
        if self.config.image != val:
            self.config.image = val
            self.config.save()

    def _image_clean(self, image=None):
        if image == None:
            return self.config.image
        if ":" in image:
            image = image.split(":")[0]
        return image

    @property
    def name(self):
        return self.config.name

    def install(self, update=True, stop=False, delete=False):
        return self.start(update=update, stop=stop, delete=delete, mount=True)

    def start(self, stop=False, delete=False, update=False, ssh=None, mount=None, pull=False, image=None, portmap=True):
        """
        @param mount : will mount the code dir from the host or not, default True
            True means: will force the mount
            None means: don't check mounted or not
            False means: will make sure is not mounted
        @param stop: stop the container if it was started
        @param delete: delete the container if it was there
        @param update: update ubuntu and some required base modules
        @param ssh: make sure ssh has been configured so you can access if from local
            True means: use ssh & configure
            None means: don't impact sshconfig, just leave as it is right now, don't do anything
            False means: remove ssh config if there is one

        @param image: can overrule the specified image at config time, normally leave empty

        @param portmap: if you want to map ports from host to docker container

        """
        if not self.container_exists_config:
            raise j.exceptions.Operations("ERROR: cannot find docker with name:%s, cannot start" % self.name)

        if pull:
            # lets make sure we have the latest image, ONLY DO WHEN FORCED, NOT STD
            j.core.tools.execute(f"docker image pull {image}", interactive=True)
            stop = True  # means we need to stop now, because otherwise we can't know we start from right image

        if delete:
            self.delete()
        else:
            if stop:
                self.stop()

        if self.isrunning():
            if mount == True:
                if not self.mount_code_exists:
                    assert image == None  # because we are creating a new image, so cannot overrule
                    image = self._internal_image_save(stop=True)
            elif mount == False:
                if self.mount_code_exists:
                    assert image == None
                    image = self._internal_image_save(stop=True)

        if not image:
            image = self.config.image
        if ":" in image:
            image = image.split(":")[0]

        if self.isrunning():
            # means we did not start because of any mismatch, so we can return
            # if people want to make sure its new situation they need to force a stop
            if update or ssh:
                self._update(update=update, ssh=ssh)
            return

        # Now create the container
        DIR_CODE = j.core.myenv.config["DIR_CODE"]
        DIR_BASE = j.core.myenv.config["DIR_BASE"]

        MOUNTS = ""
        if mount:
            MOUNTS = f"""
            -v {DIR_CODE}:/sandbox/code \
            -v {DIR_BASE}/var/containers/shared:/sandbox/myhost
            """
            MOUNTS = j.data.text.strip(MOUNTS)
        else:
            MOUNTS = f"-v {DIR_BASE}/var/containers/shared:/sandbox/myhost"

        if portmap:
            PORTRANGE = self.config.ports_txt
        else:
            PORTRANGE = ""

        if DockerFactory.image_name_exists(f"internal_{self.config.name}:") != False:
            image = f"internal_{self.config.name}"

        run_cmd = f"docker run --name={self.config.name} --hostname={self.config.name} -d {PORTRANGE} \
        --device=/dev/net/tun --cap-add=NET_ADMIN --cap-add=SYS_ADMIN --cap-add=DAC_OVERRIDE \
        --cap-add=DAC_READ_SEARCH {MOUNTS} {image} {self.config.startupcmd}"

        run_cmd = j.data.text.strip(run_cmd)
        run_cmd2 = j.data.text.replace(re.sub("\s+", " ", run_cmd))

        print(" - Docker machine gets created: ")
        print(run_cmd2)
        j.core.tools.execute(run_cmd2, interactive=False)

        self._update(update=update, ssh=ssh)

        if not mount:
            # mount the code in the container to the right location to let jumpscale work
            assert self.mount_code_exists == False
            self.dexec("rm -rf /sandbox/code")
            self.dexec("mkdir -p /sandbox/code/github")
            self.dexec("ln -s /sandbox/code_org /sandbox/code/github/threefoldtech")

        self._log("start done")

    def _update(self, update=False, ssh=False):

        if True or ssh or update or not self.config.done_get("ssh"):
            print(" - Configure / Start SSH server")

            self.dexec("rm -rf /sandbox/cfg/keys")
            self.dexec("rm -f /root/.ssh/authorized_keys;/etc/init.d/ssh stop 2>&1 > /dev/null", die=False)
            self.dexec("/usr/bin/ssh-keygen -A")
            self.dexec("/etc/init.d/ssh start")
            self.dexec("rm -f /etc/service/sshd/down")

            # get our own loaded ssh pub keys into the container
            SSHKEYS = j.core.tools.execute("ssh-add -L", die=False, showout=False)[1]
            if SSHKEYS.strip() != "":
                self.dexec('echo "%s" > /root/.ssh/authorized_keys' % SSHKEYS)
            j.core.tools.execute("mkdir -p {0}/.ssh && touch {0}/.ssh/known_hosts".format(j.core.myenv.config["DIR_HOME"]))

            # DIDNT seem to work well, next is better
            # cmd = 'ssh-keygen -f "%s/.ssh/known_hosts" -R "[localhost]:%s"' % (
            #     j.core.myenv.config["DIR_HOME"],
            #     self.config.sshport,
            # )
            # j.core.tools.execute(cmd)

            # is to make sure we can login without interactivity
            cmd = "ssh-keyscan -H -p %s localhost >> %s/.ssh/known_hosts" % (
                self.config.sshport,
                j.core.myenv.config["DIR_HOME"],
            )
            j.core.tools.execute(cmd)

        self.dexec("mkdir -p /root/state")
        if update or not self.done_get("install_base"):
            print(" - Upgrade ubuntu")
            self.dexec("add-apt-repository ppa:wireguard/wireguard -y")
            self.dexec("apt-get update")
            self.dexec("DEBIAN_FRONTEND=noninteractive apt-get -y upgrade --force-yes")
            print(" - Upgrade ubuntu ended")
            self.dexec("apt-get install mc git -y")
            self.dexec("apt-get install python3 -y")
            self.dexec("apt-get install wget tmux -y")
            self.dexec("apt-get install curl rsync unzip redis-server htop -y")
            self.dexec("apt-get install python3-distutils python3-psutil python3-pip python3-click -y")
            self.dexec("locale-gen --purge en_US.UTF-8")
            self.dexec("apt-get install software-properties-common -y")
            self.dexec("apt-get install wireguard -y")
            self.dexec("apt-get install locales -y")
            self.done_set("install_base")

        # cmd = "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' %s" % self.name
        # rc, out, err = j.core.tools.execute(cmd, replace=False, showout=False, die=False)
        # if rc == 0:
        #     self.config.ipaddr = out.strip()
        #     self.config.save()

        # if DockerFactory.container_name_exists("3bot") and self.name != "3bot":
        #     d = DockerFactory.container_get("3bot")
        #     # print(" - Create route to main 3bot container")
        #     cmd = "ip route add 10.10.0.0/16 via %s" % d.config.ipaddr
        #     # TODO: why is this no longer done?

    @property
    def info(self):
        cmd = "docker inspect %s" % self.name
        rc, out, err = j.core.tools.execute(cmd, replace=False, showout=False, die=False)
        if rc != 0:
            raise j.exceptions.Base("could not docker inspect:%s" % self.name)
        data = json.loads(out)[0]
        return data

    def dexec(self, cmd, interactive=False, die=True):
        if "'" in cmd:
            cmd = cmd.replace("'", '"')
        if interactive:
            cmd2 = "docker exec -ti %s bash -c '%s'" % (self.name, cmd)
        else:
            cmd2 = "docker exec -t %s bash -c '%s'" % (self.name, cmd)
        j.core.tools.execute(cmd2, interactive=interactive, showout=True, replace=False, die=die)

    def shell(self, cmd=None):
        if not self.isrunning():
            self.start()
        if cmd:
            self.execute("source /sandbox/env.sh;cd /sandbox;clear;%s" % cmd, interactive=True)
        else:
            self.execute("source /sandbox/env.sh;cd /sandbox;clear;bash", interactive=True)

    def diskusage(self):
        """
        uses ncdu to visualize disk usage
        :return:
        """
        self.dexec("apt update;apt install ncdu -y;ncdu /", interactive=True)

    def execute(
        self,
        cmd,
        retry=None,
        showout=True,
        timeout=3600 * 2,
        die=True,
        jumpscale=False,
        python=False,
        replace=True,
        args=None,
        interactive=True,
    ):

        self.executor.execute(
            cmd,
            retry=retry,
            showout=showout,
            timeout=timeout,
            die=die,
            jumpscale=jumpscale,
            python=python,
            replace=replace,
            args=args,
            interactive=interactive,
        )

    def kosmos(self):
        self.execute("j.shell()", interactive=True, jumpscale=True)

    def stop(self):
        if self.container_running:
            j.core.tools.execute("docker stop %s" % self.name, showout=False)
        if self.container_exists_in_docker:
            j.core.tools.execute("docker rm -f %s" % self.name, die=False, showout=False)

    def isrunning(self):
        if self.name in DockerFactory.containers_running():
            return True
        return False

    def restart(self):
        self.stop()
        self.start()

    def delete(self):
        """
        delete & remove the path with the config file to the container
        :return:
        """
        if self.container_exists_in_docker:
            self.stop()
            j.core.tools.execute("docker rm -f %s" % self.name, die=False, showout=False)
        j.core.tools.delete(self._path)
        if DockerFactory.image_name_exists(f"internal_{self.config.name}"):
            image = f"internal_{self.config.name}"
            j.core.tools.execute("docker rmi -f %s" % image, die=True, showout=False)
        self.config.done_reset()

    @property
    def export_last_image_path(self):
        """
        readonly returns the last image created
        :return:
        """
        path = "%s/exports/%s.tar" % (self._path, self._export_image_last_version)
        return path

    @property
    def _export_image_last_version(self):
        dpath = "%s/exports/" % self._path
        highest = 0
        for item in os.listdir(dpath):
            try:
                version = int(item.replace(".tar", ""))
            except:
                j.core.tools.delete("%s/%s" % (dpath, item))
            if version > highest:
                highest = version
        return highest

    def import_(self, path=None, name=None, image=None, version=None):
        """

        :param path:  if not specified will be {DIR_BASE}/var/containers/$name/exports/$version.tar
        :param version: version of the export, if not specified & path not specified will be last in the path
        :param image: docker image name as used by docker to import to
        :param start: start the container after import
        :param mount: do you want to mount the dirs to host
        :param portmap: do you want to do the portmappings (ssh is always mapped)
        :return:
        """
        image = self._image_clean(image)

        if not path:
            if not name:
                if not version:
                    version = self._export_image_last_version
                path = "%s/exports/%s.tar" % (self._path, version)
            else:
                path = "%s/exports/%s.tar" % (self._path, name)
        if not j.core.tools.exists(path):
            raise j.exceptions.Operations("could not find import file:%s" % path)

        if not path.endswith(".tar"):
            raise j.exceptions.Operations("export file needs to end with .tar")

        self.stop()
        DockerFactory.image_remove(image)

        print("import docker:%s to %s, will take a while" % (path, self.name))
        j.core.tools.execute(f"docker import {path} {image}")
        self.config.image = image

    def export(self, path=None, name=None, version=None):
        """
        :param path:  if not specified will be {DIR_BASE}/var/containers/$name/exports/$version.tar
        :param version:
        :param overwrite: will remove the version if it exists
        :return:
        """
        dpath = "%s/exports/" % self._path
        if not j.core.tools.exists(dpath):
            j.core.tools.dir_ensure(dpath)

        if not path:
            if not name:
                if not version:
                    version = self._export_image_last_version + 1
                path = "%s/exports/%s.tar" % (self._path, version)
            else:
                path = "%s/exports/%s.tar" % (self._path, name)
        if j.core.tools.exists(path):
            j.core.tools.delete(path)
        print("export docker:%s to %s, will take a while" % (self.name, path))
        j.core.tools.execute("docker export %s -o %s" % (self.name, path))
        return path

    def _internal_image_save(self, stop=False, image=None):
        if not image:
            image = f"internal_{self.name}"
        cmd = "docker rmi -f %s" % image
        j.core.tools.execute(cmd, die=False, showout=False)
        cmd = "docker rmi -f %s:latest" % image
        j.core.tools.execute(cmd, die=False, showout=False)
        cmd = "docker commit -p %s %s" % (self.name, image)
        j.core.tools.execute(cmd)
        if stop:
            self.stop()
        return image

    def _log(self, msg):
        j.core.tools.log(msg)

    def save(self, development=False, image=None, code_copy=False, clean=False):
        """

        :param clean_runtime: remove all files not needed for a runtime environment
        :param clean_devel: remove all files not needed for a development environment and a runtime environment
        :param image:
        :return:
        """
        image = self._image_clean(image)

        DockerFactory.image_remove("internal_%s" % self.config.name)

        def export_import(image, start=True):
            image2 = image.replace("/", "_")
            image2 = self._image_clean(image2)
            self.export(name=image2)
            self.import_(name=image2)
            self.start(mount=False)

        if code_copy:
            self._log("copy code")
            self.execute(BaseInstaller.code_copy_script_get())

        if clean:
            if self.mount_code_exists:
                self._log("save first, before start again without mounting")
                self._update()
                self._internal_image_save()
                self.stop()
                self.start(mount=False, update=False)

            self.execute(BaseInstaller.cleanup_script_get(), die=False)

            self.dexec("rm -rf /sandbox/code")

            if development:
                export_import("%s_dev" % image)
                self._internal_image_save(image="%s_dev" % image)

            self.execute(BaseInstaller.cleanup_script_developmentenv_get(), die=False)

            DockerFactory.image_remove("internal_%s" % self.config.name)
            DockerFactory.image_remove("internal_%s_dev" % self.config.name)

            export_import(image=image)

        else:
            self._update()
            self._internal_image_save()

        DockerFactory.image_remove("internal_%s" % self.config.name)

        self.config.save()

        # remove authorized keys
        self.dexec("rm -f /root/.ssh/*")
        self._internal_image_save(image=image)

        self.stop()
        self.delete()

    def push(self, image=None):
        if not image:
            image = self.image
        cmd = "docker push %s" % image
        j.core.tools.execute(cmd)

    def _install_tcprouter(self):
        """
        Install tcprouter builder to be part of the image
        """
        self.execute(". /sandbox/env.sh; kosmos 'j.builders.network.tcprouter.install()'")

    # def config_jumpscale(self):
    #     ##no longer ok, intent was to copy values from host but no longer the case
    #     CONFIG = {}
    #     for i in [
    #         "USEGIT",
    #         "DEBUG",
    #         "LOGGER_INCLUDE",
    #         "LOGGER_EXCLUDE",
    #         "LOGGER_LEVEL",
    #         # "LOGGER_CONSOLE",
    #         # "LOGGER_REDIS",
    #         "SECRET",
    #     ]:
    #         if i in j.core.myenv.config:
    #             CONFIG[i] = MyEnv.config[i]
    #
    #     j.core.tools.config_save(self._path + "/cfg/jumpscale_config.toml", CONFIG)
    #

    def install_jumpscale(
        self, secret=None, privatekey=None, force=False, threebot=True, pull=False, branch=None, update=False
    ):
        redo = force  # is for jumpscale only
        if not force:
            if not self.executor.state_exists("STATE_JUMPSCALE"):
                force = True

        if not force and threebot:
            if not self.executor.state_exists("STATE_THREEBOT"):
                force = True

        if not force:
            return

        args_txt = ""
        if secret:
            args_txt += " --secret='%s'" % secret
        if privatekey:
            args_txt += " --privatekey='%s'" % privatekey
        if redo:
            args_txt += " -r"
        if threebot:
            args_txt += " --threebot"
        if pull:
            args_txt += " --pull"
        if branch:
            args_txt += " --branch %s" % branch
        if not MyEnv.interactive:
            args_txt += " --no-interactive"

        dirpath = os.path.dirname(inspect.getfile(Tools))
        if dirpath.startswith(MyEnv.config["DIR_CODE"]):
            self.execute(
                """
            rm -f /tmp/InstallTools.py
            rm -f /tmp/jsx
            ln -s /sandbox/code/github/threefoldtech/jumpscaleX_core/install/jsx.py /tmp/jsx
            """
            )
        else:
            print(" - copy installer over from where I install from")
            # TODO: use executor upload function
            for item in ["jsx", "InstallTools.py"]:
                src1 = "%s/%s" % (dirpath, item)
                cmd = "scp -P {} -o StrictHostKeyChecking=no \
                    -o UserKnownHostsFile=/dev/null \
                    -r {} root@localhost:/tmp/".format(
                    self.config.sshport, src1
                )
                j.core.tools.execute(cmd)

        cmd = f"""
        cd /tmp
        python3 ./jsx configure --sshkey {MyEnv.sshagent.key_default_name} -s
        python3 ./jsx install -s {args_txt}
        """
        print(" - Installing jumpscaleX ")
        self.execute(cmd, retry=2)

        k = """
        install succesfull:
        """

        self.executor.state_set("STATE_JUMPSCALE")
        if threebot:
            self.executor.state_set("STATE_THREEBOT")

    def install_jupyter(self, force=False):
        if force:
            self.execute("j.servers.notebook.install(force=True)", jumpscale=True)
        else:
            self.execute("j.servers.notebook.install()", jumpscale=True)

    def __repr__(self):
        return "# CONTAINER: \n %s" % j.core.tools._data_serializer_safe(self.config.__dict__)

    __str__ = __repr__

    @property
    def wireguard(self):
        if not self._wireguard:
            self._wireguard = WireGuardServer(addr="127.0.0.1", port=self.config.sshport, myid=199)
        return self._wireguard


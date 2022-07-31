import os
import uuid
import shutil
import tempfile
import typing
import glob

import aws_cdk.aws_lambda as cdk_lambda
import docker


class PackageAssetCode:
    PYTHON_EXCLUDES = [
        "boto3",
        "botocore",
        "s3transfer",
        "jmespath",
        ".venv",
        "venv",
        ".pytest_cache",
        "__pycache__",
    ]

    @property
    def is_inline(self) -> bool:
        return False

    @classmethod
    def from_python_asset(
        cls, path: str, docker_image: str = "lambci/lambda:build-python3.8"
    ) -> cdk_lambda.AssetCode:
        dist = os.path.join(".", "cdk.out", f"package.{uuid.uuid4().hex}.zip")

        _package_python_asset(path, dist, docker_image)

        return cdk_lambda.AssetCode(dist)

    @classmethod
    def from_python_inline(
        cls,
        source: str,
        requirements: typing.Sequence[str] = [],
        docker_image: str = "lambci/lambda:build-python3.8",
    ) -> cdk_lambda.AssetCode:
        with tempfile.TemporaryDirectory() as workpath:
            with open(os.path.join(workpath, "requirements.txt"), "w") as file:
                for requirement in requirements:
                    file.write(f"{requirement}\n")

            with open(os.path.join(workpath, "index.py"), "w") as file:
                file.write(source)

            return cls.from_python_asset(workpath, docker_image=docker_image)


def _package_python_asset(
    path: str,
    output: str,
    docker_image: str,
    excludes: typing.Sequence[str] = PackageAssetCode.PYTHON_EXCLUDES,
) -> None:
    with tempfile.TemporaryDirectory() as work_path:
        build_path = os.path.join(work_path, "build")
        dist_path = os.path.join(work_path, "dist")

        # print("Preparing working directory...")
        os.mkdir(dist_path)

        # print("Copying application to build path...")
        shutil.copytree(path, build_path)

        # print("Installing dependencies [running in Docker]...")
        client = docker.from_env()
        client.containers.run(
            image=docker_image,
            command="/bin/sh -c 'python3 -m pip install --target /var/task/ --requirement /var/task/requirements.txt '",
            remove=True,
            volumes={build_path: {"bind": "/var/task", "mode": "rw"}},
            user=0,
        )

        for exclude in excludes:
            pattern = os.path.join(build_path, "**", exclude)

            paths = glob.glob(pattern, recursive=True)
            for path in paths:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    print(f"Couldn't remove {path} from build")

        # print("Packaging application into zip file...")
        zip_filename = shutil.make_archive(
            base_name=os.path.join(dist_path, "app"),
            format="zip",
            root_dir=build_path,
            verbose=True,
        )

        shutil.move(zip_filename, output)
        # print(f"Application packaged into [{self.output}]")

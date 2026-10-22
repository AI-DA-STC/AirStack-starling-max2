# Exploration image: CMU AirStack robot image + cuVSLAM (PyCuVSLAM) + GTSAM.
# Layered ON TOP of the CMU image; the CMU image itself is never modified.
# Build: ./docker/build.sh    Run: ./docker/run.sh
FROM airlab-docker.andrew.cmu.edu/airstack/airstack:v0.18.0_robot-x86-64_dev

ARG CUVSLAM_WHEEL=cuvslam-17.0.1+cu12-cp312-abi3-manylinux_2_39_x86_64.whl

# cuVSLAM cu12 wheel bundles cudart 12.6 but links cuBLAS/cuSPARSE/cuSOLVER 12
# (readelf NEEDED: libcublas.so.12 libcusparse.so.12 libcusolver.so.11).
# The CMU image is a CUDA 13 base, so add the 12.6 runtime libs from the NVIDIA
# apt repo that is already configured in the image (/etc/apt/sources.list.d/cuda.list).
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libcublas-12-6 libcusparse-12-6 libcusolver-12-6 libnvjitlink-12-6 \
    && rm -rf /var/lib/apt/lists/* \
    && echo "/usr/local/cuda-12.6/lib64" > /etc/ld.so.conf.d/cuda-12-6.conf && ldconfig

COPY downloads/${CUVSLAM_WHEEL} /tmp/${CUVSLAM_WHEEL}
RUN pip3 install --break-system-packages /tmp/${CUVSLAM_WHEEL} pyyaml \
    && pip3 install --break-system-packages gtsam pyulog \
    && rm -f /tmp/${CUVSLAM_WHEEL}

# Import check (no GPU at build time, so only the Python import and lib resolution).
RUN python3 -c "import cuvslam, gtsam; print('cuvslam', cuvslam.__version__ if hasattr(cuvslam,'__version__') else 'ok', 'gtsam ok')" \
    && ldd /usr/local/lib/python3.12/dist-packages/cuvslam/libcuvslam.so | grep -E "cublas|cusparse|cusolver|cudart" 

WORKDIR /exploration

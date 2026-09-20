FROM python:3.11-slim

WORKDIR /workspace

COPY ml_factory/requirements.txt /tmp/ml_factory_requirements.txt
RUN pip install --no-cache-dir -r /tmp/ml_factory_requirements.txt

COPY ml_factory /workspace/ml_factory

ENV PYTHONPATH=/workspace

CMD ["python", "-m", "ml_factory.main", "--target", "stockout"]
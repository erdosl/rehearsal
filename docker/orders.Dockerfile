ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-exercise.lock /app/
COPY wheels /wheels
RUN python -m pip install --no-index --find-links /wheels --no-cache-dir --require-hashes -r requirements-exercise.lock
COPY src/rehearsal_orders /app/rehearsal_orders
COPY src/rehearsal_exercise /app/rehearsal_exercise
USER 10001:10001
CMD ["python", "-m", "rehearsal_orders"]

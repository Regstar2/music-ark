# download-task

## Назначение

Задача на получение файла. Описывает процесс загрузки или импорта, а не сам трек.

## Отвечает за

- хранить тип задачи;
- хранить статус и прогресс;
- хранить ссылку на [[track-source]];
- хранить целевую папку;
- хранить ошибку при сбое;
- ссылаться на итоговый [[local-audio-file]];

## Возможные поля

- id;
- task_type;
- source_id;
- provider_id;
- status;
- progress;
- target_folder;
- created_at;
- started_at;
- finished_at;
- error_message;
- result_local_file_id;
- raw_payload;

## Связи

- [[download-task]] -> [[download-system]]
- [[download-task]] -> [[download-provider]]
- [[download-task]] -> [[track-source]]
- [[download-task]] -> [[local-audio-file]]
- [[download-task]] -> [[history-audit-log]]
- [[download-task]] -> [[download-queue-ui]]

## Примечания

Статусы: pending, queued, running, paused, completed, failed, cancelled, needs_review.

## Реализация v0.5

`DownloadTask` реализован в `src/musicark/download/models.py` и хранится
в таблице `download_tasks` через `DownloadStorageRepository`.

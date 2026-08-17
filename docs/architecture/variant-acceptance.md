# Variant Acceptance

`Variant Acceptance` — отдельное пользовательское решение поверх результата [[variant-detection]].

## Зачем

Анализатор может определить локальную запись как:

- `altered`;
- `different_version`;
- `uncertain`.

Это не всегда означает, что пользователю нужна замена файла. Например, другая редакция трека может быть намеренно сохранённой версией.

На экране [[matching-engine]] пользователь может нажать **«Эта версия меня устраивает»**.

## Инвариант

Принятие **не меняет** результат анализатора. Если анализатор нашёл `different_version`, запись в `track_variant_results` остаётся `different_version`.

Решение хранится отдельно в `variant_user_acceptance` и привязано к provider identity, local file ID, исходному variant status, fingerprint provider metadata, fingerprint локального аудио, fingerprint reference audio, analyzer version и времени сохранённого анализа.

Если эти признаки перестают совпадать, старое принятие считается недействительным.

## Coverage / Sync

Для принятого **текущего** результата `altered / different_version / uncertain` Coverage и Controlled Sync считают review-блокер разрешённым. При этом исходный анализ можно по-прежнему увидеть на экране сопоставления.

Это решение:

- не создаёт и не меняет Identity Matching;
- не меняет confidence;
- не переписывает аудиофайл;
- не меняет теги;
- не меняет Яндекс Музыку;
- не превращает analyzer result в `same` в `track_variant_results`.

## Отмена

Пользователь может нажать **«Отменить принятие»**. После этого review-статус снова становится значимым для Coverage / Sync.

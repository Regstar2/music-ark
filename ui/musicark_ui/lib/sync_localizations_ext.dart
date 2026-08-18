import 'l10n/app_localizations.dart';

/// Sync presentation copy assembled exclusively from the existing generated
/// RU/EN localization catalog. v0.9.6 introduces no second localization store;
/// this adapter keeps SyncPage free of hard-coded user-facing strings while
/// reusing the vocabulary already shared by Coverage, Downloads and Matching.
extension SyncLocalizations on AppLocalizations {
  String get syncTitle => navSync;
  String get syncSubtitle => helpSyncBody;
  String get syncRefresh => refresh;
  String get syncScopeLabel => coverageCollectionLabel;
  String get syncFolderLabel => downloadsTargetFolder;
  String get syncFolderNotSelected => downloadsTargetChoose;
  String get syncChangeFolder => downloadsChange;
  String get syncChooseFolder => downloadsChoose;
  String get syncSelectFolderFirst => coverageDownloadTargetRequired;
  String get syncNothingNewQueued => downloadsNoNewTasks;
  String get syncNothingNewAttention => helpSyncBody;
  String get syncNothingNewComplete => downloadsNoNewTasks;
  String get syncConfirmTitle => navSync;
  String syncConfirmQueueCount(int count) => downloadsWantedCount(count);
  String get syncSafetyNote => helpSyncBody;
  String get syncConfirmAction => navSync;
  String syncApplyResult(int enqueued, int skipped, int failed) =>
      '${downloadsAddedTasks(enqueued)} · $downloadsStatusSkipped: $skipped · '
      '$downloadsSummaryErrors: $failed';
  String get syncHideError => close;
  String get syncCalculating => matchingRunning;

  String get syncStatusReadyTitle => downloadsDownloadWanted;
  String get syncStatusMixedTitle => coverageNeedsReview;
  String get syncStatusQueuedTitle => downloadsSummaryQueued;
  String get syncStatusAttentionTitle => coverageNeedsReview;
  String get syncStatusCompleteTitle => downloadsNoNewTasks;
  String syncReadyBody(int count) => downloadsWantedCount(count);
  String syncAttentionBody(int count) => matchingFilterConflict(count);
  String syncQueuedBody(int count) => downloadsTabTasks(count);
  String get syncStatusCompleteBody => helpSyncBody;
  String get syncOpenDownloads => navDownloads;
  String syncSynchronizeTracks(int count) =>
      count > 0 ? '$navSync $count' : navSync;

  String get syncCoverageTitle => coverageSummaryTitle;
  String syncCoverageTrackTransition(int current, int projected) =>
      '$current → $projected';
  String syncCoverageCurrent(String percent) =>
      '$coverageSummaryCovered: $percent%';
  String syncCoverageProjected(String percent) =>
      '$downloadsSummaryCompleted: $percent%';

  String get syncMetricYandex => matchingSummaryYandex;
  String get syncMetricLocal => matchingSummaryLocal;
  String get syncMetricDownload => coverageDownload;
  String get syncMetricQueued => downloadsSummaryQueued;
  String get syncMetricAttention => coverageNeedsReview;

  String get syncPlanTitle => navSync;
  String syncPlanScope(String scope) => '$coverageCollectionLabel: $scope';
  String syncPlanShown(int shown, int total) => matchingShownCount(shown, total);
  String syncFilterAll(int count) => matchingFilterAll(count);
  String syncFilterDownload(int count) => '$coverageDownload $count';
  String syncFilterDecision(int count) => '$coverageDecisionLabel $count';
  String syncFilterMatching(int count) => '$navMatching $count';
  String syncFilterVariant(int count) => '$coverageVariantTitle $count';
  String syncFilterLocalOnly(int count) => '$localLibraryTitle $count';
  String get syncNoOperations => coverageEmptyFiltered;

  String get syncColumnTrack => localColumnTrack;
  String get syncColumnAction => coverageDecisionLabel;
  String get syncColumnReason => coverageDetailsReason;
  String get syncColumnStatus => matchingColumnStatus;

  String get syncDownloadAction => coverageDownload;
  String get syncIgnoreAction => coverageIgnore;
  String get syncOpenMatching => coverageOpenMatching;
  String get syncCheckVariant => matchingCheckVariants;
  String get syncActionDownload => coverageDownload;
  String get syncActionDecision => coverageDecisionLabel;
  String get syncActionMatching => navMatching;
  String get syncActionVariant => coverageVariantTitle;
  String get syncActionLocalOnly => localLibraryTitle;
  String get syncReasonWillQueue => coverageDownloadQueued;
  String get syncReasonMissing => downloadsNoLocalCopy;
  String get syncReasonMatchingRequired => coverageEmptyRunMatching;
  String get syncReasonMatchingReview => coverageNeedsReview;
  String syncReasonVariant(String variant) => '$coverageVariantTitle: $variant';
  String get syncReasonOutsideScope => localLibraryTitle;
  String get syncReasonLocalOnly => localLibraryTitle;
  String get syncStatusReady => coverageDownloadQueued;
  String get syncStatusInformational => coverageStatusUnknown;
  String get syncAllLibrary => coverageAllLibrary;
  String get syncUnknownTrack => localUnknownTrack;
  String get syncUnknownArtist => localUnknownArtist;
}

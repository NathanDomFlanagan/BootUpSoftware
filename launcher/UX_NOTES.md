# UX rough edges

Small UI polish items identified during review, kept here in case any of
them are worth revisiting later. None of these are bugs — the app behaves
correctly either way — just things that could be nicer.

## Fixed

- [x] Inconsistent button colors between the Category row and Profile row
      (`ui.py`) — both now use the same mapping: `New = green`,
      `Rename/Edit = blue`, `Delete = red`.
- [x] "Add App" picker showed only the app name, with no path column or
      tooltip (`ui.py`, `_open_app_picker`) — two Start Menu shortcuts with
      the same display name (e.g. two installed versions, or the same app
      listed in two Start Menu folders) were indistinguishable. Now shows a
      Path column plus a hover tooltip, matching the main app list.
- [x] `edit_profile`'s category checklist had no scrollbar (`ui.py`) — fixed
      `300x400` window; with enough categories, the list ran past the bottom
      with no way to reach the rest except manually dragging the window
      taller. Now wrapped in a `Canvas` + `Scrollbar`, scrollable by
      scrollbar or mouse wheel, and the inner frame resizes to match the
      window width if it's dragged wider.
- [x] Undo button was always visible, usually disabled (`ui.py`, status bar)
      — it sat in the status bar taking up space even when there was
      nothing to undo. Now hidden entirely (`pack_forget()`) until
      `last_deleted` is set, and re-appears pinned to the far right via
      `_refresh_undo_button()`.

## Open

None currently — all identified rough edges have been addressed.

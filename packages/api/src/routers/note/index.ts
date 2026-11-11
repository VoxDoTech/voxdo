import { audioUrl } from "./audio-url";
import { byId } from "./by-id";
import { create } from "./create";
import { createVoice } from "./create-voice";
import { deleteNote } from "./delete";
import { list } from "./list";
import { update } from "./update";

export const noteRouter = {
  list,
  byId,
  create,
  createVoice,
  update,
  // `delete` is a reserved word — aliased from deleteNote
  delete: deleteNote,
  audioUrl,
};

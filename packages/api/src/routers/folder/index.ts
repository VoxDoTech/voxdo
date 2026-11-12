import { create } from "./create";
import { deleteFolder } from "./delete";
import { list } from "./list";
import { update } from "./update";

export const folderRouter = {
  list,
  create,
  update,
  // `delete` is a reserved word — aliased from deleteFolder
  delete: deleteFolder,
};

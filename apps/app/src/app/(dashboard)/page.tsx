import { SiteHeader } from "~/components/layout";
import { NotesApp } from "~/components/notes/notes-app";

export default function Page() {
  return (
    <>
      <SiteHeader title="Заметки" />
      <NotesApp />
    </>
  );
}

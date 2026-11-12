import { SiteHeader } from "~/components/layout";
import { NoteDetail } from "~/components/notes/note-detail";

export default async function NotePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <>
      <SiteHeader title="Заметка" />
      <div className="flex flex-1 flex-col p-4 md:p-6">
        <NoteDetail noteId={id} />
      </div>
    </>
  );
}

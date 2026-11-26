import type { ReactNode } from "react";
import { Card } from "../kit";

export default function InfoPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <h1>{title}</h1>
      <Card>
        <p>{children}</p>
      </Card>
    </>
  );
}

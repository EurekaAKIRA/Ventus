import { useEffect, useRef } from "react";
import { mountVueAgentDialogue, type VueAgentDialogueProps } from "../vue/VueAgentDialogue";

export default function VueAgentDialogueMount(props: VueAgentDialogueProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!rootRef.current) return;
    const app = mountVueAgentDialogue(rootRef.current, props);
    app.mount(rootRef.current);
    return () => {
      app.unmount();
    };
  }, [props]);

  return <div ref={rootRef} className="vue-agent-dialogue-mount" />;
}

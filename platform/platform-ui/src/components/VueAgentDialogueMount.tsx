import { useEffect, useRef } from "react";
import { reactive, type App as VueApp } from "vue";
import { mountVueAgentDialogue, type VueAgentDialogueProps } from "../vue/VueAgentDialogue";

export default function VueAgentDialogueMount(props: VueAgentDialogueProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const appRef = useRef<VueApp | null>(null);
  const propsRef = useRef(reactive({ ...props }));

  useEffect(() => {
    Object.assign(propsRef.current, props);
  }, [props]);

  useEffect(() => {
    if (!rootRef.current || appRef.current) return;
    const app = mountVueAgentDialogue(rootRef.current, propsRef.current);
    app.mount(rootRef.current);
    appRef.current = app;
    return () => {
      appRef.current?.unmount();
      appRef.current = null;
    };
  }, []);

  return <div ref={rootRef} className="vue-agent-dialogue-mount" />;
}

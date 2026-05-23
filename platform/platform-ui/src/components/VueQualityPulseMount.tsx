import { useEffect, useRef } from "react";
import { mountVueQualityPulse, type VueQualityPulseProps } from "../vue/VueQualityPulse";

export default function VueQualityPulseMount(props: VueQualityPulseProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!rootRef.current) return;
    const app = mountVueQualityPulse(rootRef.current, props);
    app.mount(rootRef.current);
    return () => {
      app.unmount();
    };
  }, [props]);

  return <div ref={rootRef} className="vue-quality-pulse-mount" />;
}

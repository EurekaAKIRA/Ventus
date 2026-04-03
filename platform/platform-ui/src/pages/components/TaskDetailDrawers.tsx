import { Drawer, Empty, Spin } from "antd";
import JsonViewer from "../../components/JsonViewer";
import type { TaskArtifactContent } from "../../types";

type TaskDetailDrawersProps = {
  artifactDrawerOpen: boolean;
  activeArtifact: TaskArtifactContent | null;
  artifactLoading: boolean;
  onCloseArtifactDrawer: () => void;
  rawDrawerTitle: string;
  rawDrawerOpen: boolean;
  rawDrawerData: unknown;
  onCloseRawDrawer: () => void;
};

export function TaskDetailDrawers(props: TaskDetailDrawersProps) {
  const {
    artifactDrawerOpen,
    activeArtifact,
    artifactLoading,
    onCloseArtifactDrawer,
    rawDrawerTitle,
    rawDrawerOpen,
    rawDrawerData,
    onCloseRawDrawer,
  } = props;

  return (
    <>
      <Drawer
        title={activeArtifact ? `产物：${activeArtifact.type}` : "产物"}
        open={artifactDrawerOpen}
        onClose={onCloseArtifactDrawer}
        width={680}
      >
        {artifactLoading ? (
          <Spin />
        ) : !activeArtifact ? (
          <Empty description="暂无产物内容" />
        ) : typeof activeArtifact.content === "string" ? (
          <pre className="feature-text">{activeArtifact.content}</pre>
        ) : (
          <JsonViewer data={activeArtifact.content} />
        )}
      </Drawer>

      <Drawer title={rawDrawerTitle} open={rawDrawerOpen} onClose={onCloseRawDrawer} width={760}>
        {rawDrawerData == null ? (
          <Empty description="暂无原始数据" />
        ) : typeof rawDrawerData === "string" ? (
          <pre className="feature-text raw-text-viewer">{rawDrawerData}</pre>
        ) : (
          <JsonViewer data={rawDrawerData} />
        )}
      </Drawer>
    </>
  );
}

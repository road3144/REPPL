package com.a401.reppl.controller.dto;

import com.a401.reppl.service.dto.JobCreateCommand;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JobCreateRequest {

    @NotBlank(message = "videoKey는 필수입니다.")
    private String videoKey;

    @NotEmpty(message = "refImageKeys는 최소 1개 이상이어야 합니다.")
    private List<String> refImageKeys;

    @NotNull(message = "roi는 필수입니다.")
    private RoiInfo roi;

    private Map<String, Object> options;

    public JobCreateCommand toCommand() {
        return JobCreateCommand.builder()
                .videoKey(videoKey)
                .refImageKeys(refImageKeys)
                .roi(convertRoi())
                .options(options)
                .build();
    }

    private JobCreateCommand.RoiInfo convertRoi() {
        if (roi == null) {
            return null;
        }

        JobCreateCommand.RoiFrame frame = null;
        if (roi.getFrame() != null) {
            frame = JobCreateCommand.RoiFrame.builder()
                    .type(roi.getFrame().getType())
                    .timestampMs(roi.getFrame().getTimestampMs())
                    .build();
        }

        List<JobCreateCommand.RoiBox> boxes = null;
        if (roi.getBoxes() != null) {
            boxes = roi.getBoxes().stream()
                    .map(box -> JobCreateCommand.RoiBox.builder()
                            .id(box.getId())
                            .x(box.getX())
                            .y(box.getY())
                            .w(box.getW())
                            .h(box.getH())
                            .build())
                    .collect(Collectors.toList());
        }

        return JobCreateCommand.RoiInfo.builder()
                .frame(frame)
                .coordinateSystem(roi.getCoordinateSystem())
                .boxes(boxes)
                .build();
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoiInfo {
        private RoiFrame frame;
        private String coordinateSystem;
        private List<RoiBox> boxes;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoiFrame {
        private String type;
        private Long timestampMs;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoiBox {
        private String id;
        private Double x;
        private Double y;
        private Double w;
        private Double h;
    }
}

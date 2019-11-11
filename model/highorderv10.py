import torch
import torch.nn as nn
import torch.nn.functional as F
from backbone.resnet import resnet


class Kernel_Calculate(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=1, stride=1, padding=0):
        super(Kernel_Calculate, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels,
                              kernel_size=kernel_size, stride=stride, padding=padding)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        self.init_weight()

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None: nn.init.constant_(ly.bias, 0)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x

class ConvBNReLU(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1, dilation=1):
        super(ConvBNReLU, self).__init__()
        self.conv = nn.Conv2d(in_channels, out_channels,
                              kernel_size=kernel_size, stride=stride,
                              padding=padding, dilation=dilation, bias=True)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.init_weight()


    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None: nn.init.constant_(ly.bias, 0)

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        return x

class Three_Order_Module(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(Three_Order_Module, self).__init__()

        self.order3_1 = Kernel_Calculate(in_channels, out_channels)
        self.order3_2 = Kernel_Calculate(in_channels, out_channels)
        self.order3_3 = Kernel_Calculate(in_channels, out_channels)

        self.order2_1 = Kernel_Calculate(in_channels, out_channels)
        self.order2_2 = Kernel_Calculate(in_channels, out_channels)

        self.order1_1 = Kernel_Calculate(in_channels, out_channels)


        self.init_weight()

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None: nn.init.constant_(ly.bias, 0)



    def forward(self, x):
        x_order3_1 = self.order3_1(x)
        x_order3_2 = self.order3_2(x)
        x_order3_3 = self.order3_3(x)
        x_order3 = x_order3_1 * x_order3_2 * x_order3_3

        x_order2_1 = self.order2_1(x)
        x_order2_2 = self.order2_2(x)
        x_order2 = x_order2_1 * x_order2_2

        x_order1 = self.order1_1(x)


        return x_order1, x_order2, x_order3



class Kernel_Representation(nn.Module):
    def __init__(self):
        super(Kernel_Representation, self).__init__()
        self.x1_order3 = Three_Order_Module(256, 256)
        self.x2_order3 = Three_Order_Module(512, 256)
        self.x3_order3 = Three_Order_Module(1024, 256)
        self.x4_order3 = Three_Order_Module(2048, 1280)

        self.order1_conv = ConvBNReLU(2048, 2048, 1, stride=1, padding=0)
        self.order2_conv = ConvBNReLU(2048, 2048, 1, stride=1, padding=0)
        self.order3_conv = ConvBNReLU(2048, 2048, 1, stride=1, padding=0)

        self.maxpool = nn.MaxPool2d(kernel_size=2, stride=2)

        self.init_weight()

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None: nn.init.constant_(ly.bias, 0)


    def forward(self, x1, x2, x3, x4):
        x1_order1, x1_order2, x1_order3 = self.x1_order3(self.maxpool(self.maxpool(x1)))
        x2_order1, x2_order2, x2_order3 = self.x2_order3(self.maxpool(x2))
        x3_order1, x3_order2, x3_order3 = self.x3_order3(x3)
        x4_order1, x4_order2, x4_order3 = self.x4_order3(x4)


        order1 = torch.cat((x4_order1, x3_order1, x2_order1, x1_order1), dim=1)
        order2 = torch.cat((x4_order2, x3_order2, x2_order2, x1_order2), dim=1)
        order3 = torch.cat((x4_order3, x3_order3, x2_order3, x1_order3), dim=1)

        order1 = self.order1_conv(order1)
        order2 = self.order2_conv(order2)
        order3 = self.order3_conv(order3)

        return order1, order2, order3


class Feature_Fusion(nn.Module):
    def __init__(self):
        super(Feature_Fusion, self).__init__()

        self.featurefusion1 = ConvBNReLU(2048, 256, padding=18, dilation=18)
        self.featurefusion2 = ConvBNReLU(2048, 256, padding=12, dilation=12)
        self.featurefusion3 = ConvBNReLU(2048, 256, padding=6, dilation=6)
        self.featurefusion4 = ConvBNReLU(2048, 256, padding=1, dilation=1)

        self.avg = nn.AdaptiveAvgPool2d((1, 1))
        self.featurefusion5 = ConvBNReLU(2048, 256, kernel_size=1, stride=1, padding=0)

        self.conv_out = ConvBNReLU(256 * 5, 256, kernel_size=1, stride=1, padding=0)

        self.init_weight()

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None: nn.init.constant_(ly.bias, 0)


    def forward(self, order1, order2, order3, x4):
        H, W = x4.size()[2:]

        feat1 = self.featurefusion1(order3)
        feat2 = self.featurefusion2(order2)
        feat3 = self.featurefusion3(order1)
        feat4 = self.featurefusion4(x4)

        feat5 = self.avg(x4)
        feat5 = self.featurefusion5(feat5)
        feat5 = F.interpolate(feat5, size=(H, W), mode='bilinear', align_corners=True)

        feat = torch.cat((feat1, feat2, feat3, feat4, feat5), dim=1)

        out = self.conv_out(feat)

        return out


class HighOrder(nn.Module):
    def __init__(self, n_classes):
        super(HighOrder, self).__init__()

        self.backbone = resnet(101, 16)
        self.kernelrep = Kernel_Representation()
        self.featurefusion = Feature_Fusion()

        self.conv_low = nn.Conv2d(256, 48, kernel_size=1, stride=1, padding=0)
        self.bn1 = nn.BatchNorm2d(48)

        self.conv_cat = nn.Sequential(
            ConvBNReLU(304, 256),
            ConvBNReLU(256, 256)
        )

        self.conv_out = nn.Conv2d(256, n_classes, kernel_size=1, bias=False)

        self.relu = nn.ReLU(inplace=True)

        self.init_weight()

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None: nn.init.constant_(ly.bias, 0)


    def forward(self, x):
        x1, x2, x3, r_x4 = self.backbone(x)
        order1, order2, order3 = self.kernelrep(x1, x2, x3, r_x4)
        feat = self.featurefusion(order1, order2, order3, r_x4)

        H, W = x1.size()[2:]
        low = self.bn1(self.conv_low(x1))
        feat = F.interpolate(feat, (H, W), mode='bilinear', align_corners=True)
        cat = torch.cat((feat, low), dim=1)
        final = self.conv_cat(cat)
        final = self.conv_out(final)

        H, W = x.size()[2:]
        final = F.interpolate(final, (H, W), mode='bilinear', align_corners=True)

        return final











